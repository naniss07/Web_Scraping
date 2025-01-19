# Import necessary libraries
import streamlit as st
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
import random
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from dataclasses import dataclass
from datetime import datetime
import re

@dataclass
class StandardizedReview:
    customer_name: str
    stay_date: str
    review_text: str
    rating: float
    source: str

# Initialize Streamlit app
st.title("Hotel Customer Review Scraper")
st.markdown("Select your browser and provide URLs for Google Maps and Booking to scrape customer reviews.")

# Input fields for URLs
google_url = st.text_input("Google Maps URL", placeholder="Enter Google Maps URL")
booking_url = st.text_input("Booking.com URL", placeholder="Enter Booking.com URL")
webhook_url = st.text_input("Webhook URL", placeholder="Enter webhook URL for sending scraped data")

# Booking.com için sayfa sayısı input'u
booking_pages = st.number_input("Number of pages to scrape from Booking.com", 
                              min_value=1, 
                              max_value=20, 
                              value=5, 
                              help="Enter the number of pages you want to scrape from Booking.com (1-20)")

def initialize_driver():
    try:
        st.write("Initializing WebDriver...")
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        # ChromeDriverManager'ı doğrudan kullan
        service = ChromeService()
        driver = webdriver.Chrome(
            service=service,
            options=options
        )
        
        st.write("Chrome WebDriver initialized.")
        return driver
    except Exception as e:
        st.error(f"Error initializing WebDriver: {e}")
        return None

def standardize_rating(rating_text):
    try:
        cleaned = ''.join(c for c in rating_text if c.isdigit() or c in '.,')
        if " " in cleaned:
            cleaned = cleaned.split()[0]
        cleaned = cleaned.replace(',', '.')
        rating = float(cleaned)
        if rating > 10:
            rating = 10.0
        return round(rating, 1)
    except:
        return 0.0

def scrape_google_maps(url, driver):
    try:
        st.write("Opening Google Maps URL...")
        driver.get(url)
        st.write(f"Opened URL: {url}")

        try:
            wait = WebDriverWait(driver, 10)
            see_all_button = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "button.HHrUdb.fontTitleSmall.rqjGif")
            ))
            
            if not see_all_button:
                see_all_button = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//button[contains(@class, 'HHrUdb')]//span[contains(text(), 'yorum')]/..")
                ))
            
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", see_all_button)
            time.sleep(1)
            
            try:
                see_all_button.click()
            except:
                driver.execute_script("arguments[0].click();", see_all_button)
            
            time.sleep(2)

        except Exception as e:
            st.write(f"Could not locate or click the reviews button: {str(e)}")

        scrollable_div = None
        try:
            scrollable_div = driver.find_element(By.CSS_SELECTOR, "div.m6QErb.DxyBCb.kA9KIf.dS8AEf.XiKgde")
            st.write("Found scrollable reviews container.")
        except:
            st.write("Could not find scrollable reviews container. Using window scroll...")

        rangeval = 20
        for i in range(rangeval):
            st.write(f"Scrolling ({i + 1}/{rangeval})...")
            if scrollable_div:
                driver.execute_script("arguments[0].scrollBy(0, 3000);", scrollable_div)
            else:
                driver.execute_script("window.scrollBy(0, 3000);")
            time.sleep(random.uniform(1.0, 2.5))

            review_elements = driver.find_elements(By.CLASS_NAME, "jJc9Ad")
            st.write(f"Current review count: {len(review_elements)}")

        reviews = []
        for idx, element in enumerate(review_elements):
            try:
                customer_name = element.find_element(By.CLASS_NAME, "d4r55").text.strip()
                review_text = element.find_element(By.CLASS_NAME, "wiI7pd").text.strip()
                date = element.find_element(By.CLASS_NAME, "xRkPPb").text.strip()
                cleaned_date = date.replace("Google\n, ", "").strip()
                
                # Yeni puan çıkarma yöntemi
                rating = 0.0
                try:
                    rating_element = element.find_element(By.CLASS_NAME, "fzvQIb")
                    if rating_element:
                        rating_text = rating_element.text.strip()
                        # "5/5" formatından ilk sayıyı al
                        rating = float(rating_text.split('/')[0])
                except Exception as e:
                    st.write(f"Warning: Could not extract rating for review {idx + 1}")

                standardized_review = StandardizedReview(
                    customer_name=customer_name or "-",
                    stay_date=cleaned_date or "-",
                    review_text=review_text or "-",
                    rating=rating,
                    source="Google Maps"
                )
                reviews.append(standardized_review.__dict__)
            except Exception as e:
                st.error(f"Error processing review {idx + 1}: {e}")
                continue
        return reviews
    except Exception as e:
        st.error(f"Error scraping Google Maps: {e}")
        return []

def scrape_booking(url, driver, max_pages=5):
    try:
        st.info("Scraping Booking.com with Selenium...")
        driver.get(url)
        time.sleep(5)

        review_button_selectors = [
            "button[data-testid='fr-read-all-reviews']",
            "button.a83ed08757",
            "a[data-testid='property-reviews-link']",
            "[data-testid='pdp-reviews-trigger']"
        ]

        for selector in review_button_selectors:
            try:
                button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                time.sleep(2)
                try:
                    button.click()
                except:
                    driver.execute_script("arguments[0].click();", button)
                time.sleep(3)
                break
            except Exception:
                continue

        st.write("Loading reviews...")
        scroll_pause_time = 3
        screen_height = driver.execute_script("return window.screen.height;")

        reviews = []
        page = 1

        while page <= max_pages:
            st.write(f"Scraping page {page} of {max_pages}...")
            
            # Her sayfada scroll işlemi
            i = 1
            while i <= 3:
                driver.execute_script(f"window.scrollTo(0, {screen_height * i});")
                i += 1
                time.sleep(scroll_pause_time)
                
                try:
                    show_more_buttons = driver.find_elements(By.CSS_SELECTOR, "button.mpc-button, button[data-testid='show-more-button']")
                    for button in show_more_buttons:
                        if button.is_displayed():
                            driver.execute_script("arguments[0].click();", button)
                            time.sleep(2)
                except Exception:
                    pass

            review_selectors = [
                "div[data-testid='review']",
                "div.review_list_new_item_block",
                "[data-review-url]"
            ]
            
            review_elements = []
            for selector in review_selectors:
                review_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if review_elements:
                    st.write(f"Found {len(review_elements)} reviews on page {page}")
                    break

            for review in review_elements:
                try:
                    score_selectors = [
                        "div[data-testid='review-score']",
                        "div.ac4a7896c7",
                        "div.review-score-badge"
                    ]
                    
                    score = 0.0
                    for score_selector in score_selectors:
                        try:
                            score_element = review.find_element(By.CSS_SELECTOR, score_selector)
                            score_text = score_element.text.strip()
                            score = standardize_rating(score_text)
                            if score > 0:
                                break
                        except:
                            continue

                    try:
                        name = review.find_element(By.CSS_SELECTOR, "div.a3332d346a").text.strip()
                    except:
                        name = "Anonymous"

                    try:
                        stay_date = review.find_element(By.CSS_SELECTOR, "span[data-testid='review-stay-date']").text.strip()
                    except:
                        stay_date = "-"

                    pos_text = neg_text = ""
                    try:
                        pos_text = review.find_element(By.CSS_SELECTOR, "div[data-testid='review-positive-text']").text.strip()
                    except:
                        pass
                    
                    try:
                        neg_text = review.find_element(By.CSS_SELECTOR, "div[data-testid='review-negative-text']").text.strip()
                    except:
                        pass

                    review_data = {
                        "customer_name": name,
                        "stay_date": stay_date,
                        "review": f"Olumlu: {pos_text}\nOlumsuz: {neg_text}".strip(),
                        "rating": score,
                        "source": "Booking.com",
                        "page": page
                    }
                    
                    reviews.append(review_data)

                except Exception as e:
                    st.write(f"Error processing review: {str(e)}")
                    continue

            try:
                next_page_button = driver.find_element(By.CSS_SELECTOR, f"button[aria-label=' {page + 1}']")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_page_button)
                time.sleep(2)
                driver.execute_script("arguments[0].click();", next_page_button)
                time.sleep(3)
                page += 1
            except Exception as e:
                st.write(f"No more pages available or reached the end: {str(e)}")
                break

        st.success(f"Successfully scraped {len(reviews)} reviews from {page-1} pages on Booking.com")
        return reviews

    except Exception as e:
        st.error(f"Error scraping Booking.com: {str(e)}")
        return []

# Single button with unique key
if st.button("Scrape Customer Reviews", key="scrape_button"):
    st.info("Scraping in progress... Please wait.")
    all_reviews = []
    
    driver = initialize_driver()
    if driver:
        if google_url:
            st.write("Scraping Google Maps reviews...")
            google_reviews = scrape_google_maps(google_url, driver)
            st.write(f"Scraped {len(google_reviews)} Google Maps reviews.")
            all_reviews.extend(google_reviews)
        if booking_url:
            st.write("Scraping Booking.com reviews...")
            booking_reviews = scrape_booking(booking_url, driver, max_pages=booking_pages)
            st.write(f"Scraped {len(booking_reviews)} Booking.com reviews.")
            all_reviews.extend(booking_reviews)

        driver.quit()

        if all_reviews:
            with open("müşteri_yorumları.json", "w", encoding="utf-8") as file:
                json.dump(all_reviews, file, ensure_ascii=False, indent=4)
            st.success("Kazıma işlemi başarıyla tamamlandı. Veriler müşteri_yorumları.json dosyasına kaydedildi.")
            if webhook_url:
                try:
                    response = requests.post(webhook_url, json=all_reviews)
                    if response.status_code == 200:
                        st.success("Veriler webHook başarıyla gönderildi.")
                    else:
                        st.error(f"Webhook error: {response.status_code} - {response.text}")
                except Exception as e:
                    st.error(f"Webhook'a veri gönderilirken hata oluştu: {e}")
            else:
                st.warning("Webhook URL'si sağlanmadı. Veri gönderilmedi.")
        else:
            st.warning("Kazınmış yorum yok. Lütfen sağlanan URL'leri kontrol edin.")
