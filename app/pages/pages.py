"""Registry of top-level application pages."""

from app.pages.login_page import LoginPage
from app.pages.main_page import MainPage


PAGES_LIST = {
    "Login": LoginPage,
    "Main": MainPage,
}
