from dotenv import load_dotenv
import os
import google.generativeai as genai
from rich.console import Console
from rich.table import Table

def list_models_for_key(api_key: str):
    console = Console()
    
    try:
        genai.configure(api_key=api_key)
        models = genai.list_models()
        
        table = Table(title=f"📋 Models Available for API Key")
        table.add_column("Model Name", style="cyan")
        table.add_column("Display Name", style="green")
        table.add_column("Token Limit", style="yellow")
        table.add_column("Generation Methods", style="magenta")
        
        for model in models:
            token_limit = f"Input: {model.input_token_limit}\nOutput: {model.output_token_limit}"
            methods = "\n".join(model.supported_generation_methods)
            
            table.add_row(
                model.name,
                model.display_name,
                token_limit,
                methods
            )
        
        console.print(table)
        console.print(f"✅ Successfully listed models for API Key\n")
        
    except Exception as e:
        console.print(f"❌ Error with API Key: {str(e)}\n", style="bold red")

def main():
    load_dotenv()
    console = Console()
    
    console.print("\n🔍 Checking Available Gemini Models", style="bold blue")
    console.print("=" * 80 + "\n")
    

    key = os.getenv("GEMINI_API_KEY_3")
    if not key:
        console.print(f"⚠️  API Key not found in .env file\n", style="bold yellow")
        
    list_models_for_key("AIzaSyBTVkF8DVK5E0upSddecyYvwKJJdJqwE-E")

if __name__ == "__main__":
    main()