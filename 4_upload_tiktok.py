"""Fase 4: publica el video en TikTok automatizando el navegador con Playwright."""

import sys

from pipeline_utils import load_config, output_dir, resolve

UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"


def save_session(storage_state):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.tiktok.com/login")
        input("Inicia sesion en la ventana del navegador y pulsa Enter aqui... ")
        context.storage_state(path=str(storage_state))
        browser.close()
    print(f"Sesion guardada -> {storage_state}")


def upload(config, video_path):
    from playwright.sync_api import sync_playwright

    settings = config["tiktok"]
    storage_state = resolve(settings["storage_state"])
    if not storage_state.exists():
        raise RuntimeError(
            f"No hay sesion guardada en {storage_state}. Ejecuta: python3 4_upload_tiktok.py --login"
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=settings["headless"])
        context = browser.new_context(storage_state=str(storage_state))
        page = context.new_page()
        page.goto(UPLOAD_URL)

        page.set_input_files("input[type=file]", str(video_path))
        page.wait_for_selector("div[contenteditable=true]", timeout=120_000)

        caption = settings.get("caption")
        if caption:
            editor = page.locator("div[contenteditable=true]").first
            editor.click()
            editor.fill(caption)

        if settings.get("dry_run", True):
            print("[4/4] dry_run activo: video cargado pero no publicado.")
            input("Revisa el navegador y pulsa Enter para cerrar... ")
        else:
            page.get_by_role("button", name="Post", exact=False).click()
            page.wait_for_timeout(15_000)
            print("[4/4] Video publicado en TikTok.")

        browser.close()


def main():
    config = load_config()

    if "--login" in sys.argv:
        save_session(resolve(config["tiktok"]["storage_state"]))
        return 0

    video_path = output_dir(config) / "video.mp4"
    if not video_path.exists():
        raise FileNotFoundError(f"Ejecuta primero la fase 3: falta {video_path}")

    upload(config, video_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
