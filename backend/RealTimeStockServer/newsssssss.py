import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

def get_stock_news(ticker, days=10):
    """
    Scrapes Google Finance for the last 'days' of news for a given stock 'ticker'.
    """
    # Format the Google Finance news URL
    url = f"https://www.google.com/finance/quote/{ticker}:NASDAQ"

    # Send a request to the URL
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()  # Raise an exception for bad status codes
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return

    # Parse the HTML content
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the news articles
    news_items = soup.find_all('div', class_='yY3Lee')

    if not news_items:
        print("No news found for this ticker.")
        return

    # Get the date range
    ten_days_ago = datetime.now() - timedelta(days=days)

    print(f"Recent News for {ticker} (Last {days} Days):\n")

    for item in news_items:
        # Extract headline, source, and time
        headline_tag = item.find('h3', class_='JsuyRc')
        source_tag = item.find('div', class_='sfyJob')
        time_tag = item.find('div', class_='Adak')

        if headline_tag and source_tag and time_tag:
            headline = headline_tag.get_text()
            source = source_tag.get_text()
            time_str = time_tag.get_text()

            # --- Date Parsing Logic ---
            # This part can be tricky as the format can vary (e.g., "1 hour ago", "2 days ago")
            news_date = None
            if 'hour' in time_str or 'hours' in time_str:
                hours_ago = int(time_str.split()[0])
                news_date = datetime.now() - timedelta(hours=hours_ago)
            elif 'day' in time_str or 'days' in time_str:
                days_ago_val = int(time_str.split()[0])
                news_date = datetime.now() - timedelta(days=days_ago_val)
            # Add more conditions here if you encounter other time formats

            if news_date and news_date >= ten_days_ago:
                print(f"- {headline}")
                print(f"  Source: {source}")
                print(f"  Published: {time_str}\n")

if __name__ == "__main__":
    # Example usage: Get news for Apple (AAPL)
    get_stock_news("AAPL")