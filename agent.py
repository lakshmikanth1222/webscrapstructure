import os
import time
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from google import genai
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from tenacity import retry, stop_after_attempt, wait_exponential

console = Console()

def search_web(topic, num_results=3):
    console.print(f"\n[bold blue]Searching the web for:[/bold blue] '{topic}'...")
    ddgs = DDGS()
    try:
        results = list(ddgs.text(topic, max_results=num_results))
        urls = [res['href'] for res in results]
        console.print(f"[green]Found {len(urls)} URLs.[/green]")
        for url in urls:
            console.print(f" - [cyan]{url}[/cyan]")
        return urls
    except Exception as e:
        console.print(f"[red]Error during web search:[/red] {e}")
        return []

def scrape_url(url):
    console.print(f"Scraping: [cyan]{url}[/cyan]...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements to clean up text
        for script in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            script.decompose()
            
        text = soup.get_text(separator=' ', strip=True)
        # Limit text length to avoid token limits per page
        text = text[:15000] 
        return text
    except Exception as e:
        console.print(f"[yellow]Failed to scrape {url}:[/yellow] {e}")
        return ""

def extract_structured_data(topic, scraped_texts, output_format):
    console.print("\n[bold blue]🧠 Extracting structured data using Gemini AI...[/bold blue]")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is not set.")
        console.print("Please set it using: [yellow]$env:GEMINI_API_KEY=\"your_key\"[/yellow] (PowerShell) or [yellow]set GEMINI_API_KEY=your_key[/yellow] (CMD)")
        return None

    try:
        # We use the new google-genai library
        client = genai.Client(api_key=api_key)
    except Exception as e:
        console.print(f"[bold red]Failed to initialize Gemini Client:[/bold red] {e}")
        return None
    
    combined_text = "\n\n--- NEXT SOURCE ---\n\n".join(scraped_texts)
    
    prompt = f"""
    You are an expert data extraction AI agent.
    The user is asking about the following topic: "{topic}"
    
    I have provided scraped text from top web search results below.
    Your task is to extract "everything about the input" from this text and present it in a highly structured format.
    
    The user requested the output in this format: {output_format}
    If the requested format is "table", output a neat Markdown table.
    If the requested format is "json", output raw JSON inside a JSON code block.
    Ensure the data fields are relevant to the topic (e.g., if it's products, extract Name, Price, Features, URL, etc., if it's news, extract Title, Date, Summary, Source).
    
    --- SCRAPED TEXT ---
    {combined_text[:60000]}  # Ensuring we don't exceed typical payload sizes
    """
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_api():
        return client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
    try:
        response = _call_api()
        return response.text
    except Exception as e:
        console.print(f"[bold red]Error calling Gemini API after retries:[/bold red] {e}")
        return None

def main():
    console.print(Panel.fit("[bold magenta]Universal Web-Scraping AI Agent[/bold magenta] 🕷️🤖"))
    
    try:
        topic = input("Enter the topic or domain to scrape (e.g., 'latest graphics cards prices'): ")
        if not topic.strip():
            console.print("[red]Topic cannot be empty. Exiting.[/red]")
            return
            
        output_format = input("Enter desired output format (e.g., 'table', 'json') [default: table]: ")
        if not output_format.strip():
            output_format = "table"
            
        urls = search_web(topic, num_results=3)
        if not urls:
            return
            
        scraped_texts = []
        for url in urls:
            text = scrape_url(url)
            if text:
                scraped_texts.append(f"Source URL: {url}\n{text}")
            time.sleep(1) # Polite delay
            
        if not scraped_texts:
            console.print("[red]Could not scrape any text from the found URLs. Exiting.[/red]")
            return
            
        result = extract_structured_data(topic, scraped_texts, output_format)
        
        if result:
            console.print("\n[bold green]✅ Extraction Complete![/bold green]\n")
            if 'json' in output_format.lower():
                console.print(result)
            else:
                # Render markdown table nicely
                console.print(Markdown(result))
                
    except KeyboardInterrupt:
        console.print("\n[yellow]Process interrupted by user. Exiting.[/yellow]")

if __name__ == "__main__":
    main()
