import yfinance as yf


apple = yf.Ticker("AAPL")


# save the news into a file formated as a json array
data = apple.news
extracted_data = []
for item in data:
    content = item.get("content", {}) # Use .get for safer access to 'content'

    title = content.get("title")
    summary = content.get("summary")
    pub_date = content.get("pubDate")

    thumbnail = content.get("thumbnail")
    thumbnail_original_url = None
    if thumbnail and isinstance(thumbnail, dict): # Check if thumbnail exists and is a dictionary
        thumbnail_original_url = thumbnail.get("originalUrl")

    click_through_url_obj = content.get("clickThroughUrl")
    click_through_url = None
    if click_through_url_obj and isinstance(click_through_url_obj, dict): # Check if clickThroughUrl exists and is a dictionary
        click_through_url = click_through_url_obj.get("url")

    extracted_data.append({
        "title": title,
        "summary": summary,
        "pubDate": pub_date,
        "thumbnail_originalUrl": thumbnail_original_url,
        "clickThroughUrl_url": click_through_url
    })

def extractNewsInfo(news):
    extracted_info = []
    for item in news:
        content = item.get("content", {})
        title = content.get("title")
        summary = content.get("summary")
        pub_date = content.get("pubDate")

        thumbnail = content.get("thumbnail")
        thumbnail_original_url = None
        if thumbnail and isinstance(thumbnail, dict):
            thumbnail_original_url = thumbnail.get("originalUrl")

        click_through_url_obj = content.get("clickThroughUrl")
        click_through_url = None
        if click_through_url_obj and isinstance(click_through_url_obj, dict):
            click_through_url = click_through_url_obj.get("url")

        extracted_info.append({
            "title": title,
            "summary": summary,
            "pubDate": pub_date,
            "thumbnailURL": thumbnail_original_url,
            "newsPage": click_through_url
        })
    return extracted_info