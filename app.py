import os
import time
import requests
import cloudscraper
from bs4 import BeautifulSoup
from ddgs import DDGS
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential
from flask import Flask, render_template, request, jsonify
import markdown

app = Flask(__name__)

def search_web(topic, num_results=10):
    ddgs = DDGS()
    try:
        results = list(ddgs.text(topic, max_results=num_results))
        urls = [res['href'] for res in results]
        return urls
    except Exception as e:
        print(f"Error during web search: {e}")
        return []

def scrape_url(url):
    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            script.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return text[:15000] 
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
        return ""

def extract_structured_data(api_key, topic, scraped_texts, output_format):
    if not api_key:
        return {"error": "API key is required."}

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        return {"error": f"Failed to initialize Gemini Client: {e}"}
    
    combined_text = "\n\n--- NEXT SOURCE ---\n\n".join(scraped_texts)
    
    prompt = f"""
    You are an expert data extraction AI agent.
    The user is asking about the following topic: "{topic}"
    
    I have provided scraped text from top web search results below.
    Your task is to extract "everything about the input" from this text and present it in a highly structured format.
    
    The user requested the output in this format: {output_format}
    If the requested format is "table", output a neat Markdown table.
    If the requested format is "json", output raw JSON inside a JSON code block.
    Ensure the data fields are relevant to the topic.
    
    CRITICAL INSTRUCTION: If the scraped data contains any prices in US Dollars ($/USD), you MUST add an extra column (for table format) or field (for json format) showing the equivalent price in Indian Rupees (INR/₹). Calculate the INR price using an approximate current exchange rate. This INR column/field should ONLY be included if US Dollar prices are present in the data.
    
    --- SCRAPED TEXT ---
    {combined_text[:60000]}
    """
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_api():
        return client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
    try:
        response = _call_api()
        return {"data": response.text}
    except Exception as e:
        return {"error": f"Error calling Gemini API after retries: {e}"}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    req = request.get_json()
    api_key = req.get('api_key')
    topic = req.get('topic')
    output_format = req.get('format', 'table')
    
    if not api_key:
        return jsonify({"error": "Gemini API Key is required"}), 401
        
    if not topic:
        return jsonify({"error": "Topic is required"}), 400
        
    urls = search_web(topic, num_results=10)
    if not urls:
        return jsonify({"error": "Could not find any relevant URLs. Try a more specific search term."}), 404
        
    scraped_texts = []
    for url in urls:
        text = scrape_url(url)
        if text:
            scraped_texts.append(f"Source URL: {url}\n{text}")
            if len(scraped_texts) >= 3:
                break # We only need 3 good sources to avoid huge prompts
        time.sleep(1)
        
    if not scraped_texts:
        return jsonify({"error": "Could not extract text from the found URLs. They might be blocking bots."}), 404
        
    result = extract_structured_data(api_key, topic, scraped_texts, output_format)
    
    if "error" in result:
        return jsonify({"error": result["error"]}), 500
        
    data = result["data"]
    
    # Parse markdown if not json
    if 'json' not in output_format.lower():
        html_data = markdown.markdown(data, extensions=['tables'])
    else:
        # Strip markdown json block tags if present
        if data.startswith("```json"):
            data = data[7:]
        if data.endswith("```"):
            data = data[:-3]
        html_data = f"<pre><code>{data.strip()}</code></pre>"
        
    return jsonify({"html": html_data, "raw": data, "urls": urls})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
