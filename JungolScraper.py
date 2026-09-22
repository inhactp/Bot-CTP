import json
import sys
from io import BytesIO
from pathlib import Path
from time import sleep

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR / "data.json"

LOGIN_URL = "https://jungol.co.kr/auth/signin"



def loadCredentials() -> tuple[str, str]:
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data["id"], data["pass"]


def login(driver: webdriver.Chrome) -> None:
    user_id, password = loadCredentials()

    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 10)

    username_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username']")))
    username_field.send_keys(user_id)

    password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
    password_field.send_keys(password)

    driver.find_element(By.XPATH, "//button[not(@light-1) and contains(., '로그인')]").click()

    try:
        WebDriverWait(driver, 10).until_not(EC.url_contains("/auth/signin"))
    except Exception:
        raise RuntimeError("Login failed - still on sign-in page (check id/pass in data.json)")
    pass


def stitchScreenshots(pngs: list[bytes]) -> bytes:
    """
    Vertically combines a list of element screenshots (left-aligned) into one PNG.
    """
    images = [Image.open(BytesIO(png)) for png in pngs]
    max_width = max(img.width for img in images)
    total_height = sum(img.height for img in images)
    combined = Image.new("RGB", (max_width, total_height), "white")
    y = 0
    for img in images:
        combined.paste(img, (0, y))
        y += img.height
    buf = BytesIO()
    combined.save(buf, format="PNG")
    return buf.getvalue()


def getScoreboard(contest_id: int|str, headless: bool = True, screenshot: bool = False) -> tuple[list[dict], bytes|None]:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # jungol's scoreboard keeps a live connection open (real-time updates), which can
    # prevent the page from ever reaching Chrome's "fully loaded" state and hang
    # driver.get() until chromedriver's internal renderer timeout fires. "eager" only
    # waits for the DOM to be interactive, not for all network activity to settle.
    options.page_load_strategy = "eager"

    driver = webdriver.Chrome(options=options)
    try:
        login(driver)
        driver.get(f"https://jungol.co.kr/group/1123")
        sleep(1)
        el_members = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article.S-3wldza"))
        )[0].find_elements(By.XPATH, "./*")
        members = {"mod":[],"mem":[]}
        inc = 0
        for el in el_members:
            tag = el.tag_name.lower()
            if tag == "h2":
                #print(el.text)
                inc+=1
            elif 0<inc:
                try:
                    name = el.find_element(By.CSS_SELECTOR, "button._p").text.strip().split()[0]
                    members[[None,"mod","mod","mem"][inc]].append(name)
                except:
                    pass
            pass
        #print(members)
        
        driver.get(f"https://jungol.co.kr/contest/{contest_id}/scoreboard")
        el_names = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".S-dady6r.navLeft.leftSticky h4"))
        )
        el_scores = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".S-dady6r.navLeft.leftSticky .S-ep1uo1 span span"))
        )
        scbd = []
        for i in range(len(el_names)):
            id = el_names[i].text.strip().split()
            id,*nick = [*id]+[*id]
            nick = nick[0]
            score = el_scores[i].text.strip()
            print(id,score)
            scbd.append({"name":id,"score":int(score[0]),"mod":(id in members["mod"])})
            pass

        screenshot_bytes = None
        if screenshot:
            score_elements = driver.find_elements(By.CSS_SELECTOR, ".S-1oezert > .S-dady6r > .S-dady6r:not(:first-child)")
            if score_elements:
                screenshot_bytes = stitchScreenshots([el.screenshot_as_png for el in score_elements])

        return scbd, screenshot_bytes
    finally:
        driver.quit()
    pass


if __name__ == "__main__":
    #contest_id = int(sys.argv[1])
    scoreboard, screenshot_bytes = getScoreboard("4334", headless=False, screenshot=True)
    print(scoreboard)
    if screenshot_bytes:
        with open("scoreboard_screenshot.png", "wb") as f:
            f.write(screenshot_bytes)
    pass
