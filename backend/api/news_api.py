import requests
import os
import sys
from dotenv import load_dotenv

class QueryAPI:
    def __init__(self):
        """Initialize with Perplexity API credentials from .env file"""
        # Load API key from .env file
        load_dotenv()
        self.api_key = os.environ.get("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY not found in .env file")
            
        self.api_url = "https://api.perplexity.ai/chat/completions"
        
    def process_query(self, query):
        """
        Process any user query through the Perplexity API
        
        Args:
            query (str): The user's raw query/question
            
        Returns:
            dict: Formatted response with topic, headline, and summary
        """
        # Set up request headers
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Pass the raw query directly to Perplexity with updated payload structure
        payload = {
            "model": "sonar-pro",  # Use a model that Perplexity supports
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that provides accurate information."},
                {"role": "user", "content": query}
            ],
            "max_tokens": 1024
        }
        
        # Call Perplexity API
        try:
            response = requests.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            
            # Extract content from Perplexity's response
            result = response.json()
            response_content = result["choices"][0]["message"]["content"]
            
            # Format in your desired structure
            return {
                "topic": query,
                "headline": f"Breaking: Big News in {query.title()}!",
                "summary": response_content
            }
            
        except Exception as e:
            print(f"API Error Details: {str(e)}")
            if 'response' in locals() and hasattr(response, 'text'):
                print(f"Response text: {response.text}")
                
            return {
                "error": str(e),
                "topic": query,
                "headline": f"Error processing: {query}",
                "summary": "Unable to process this query at this time."
            }


def main():
    """Test the QueryAPI with user input or command line arguments"""
    
    try:
        # Initialize API client
        query_api = QueryAPI()
        
        # Get query from command line args or prompt user
        if len(sys.argv) > 1:
            # Use command line argument as query
            query = " ".join(sys.argv[1:])
        else:
            # Prompt user for input
            query = input("Enter your query: ")
        
        print(f"\nProcessing query: '{query}'")
        print("-" * 50)
        
        # Process the query
        result = query_api.process_query(query)
        
        # Display results
        print("\nRESULT:")
        print(f"Topic: {result['topic']}")
        print(f"Headline: {result['headline']}")
        print("\nSummary:")
        print(result['summary'])
        
        # Show error if present
        if "error" in result:
            print("\nERROR DETAILS:")
            print(result["error"])
            
    except ValueError as e:
        print(f"Error: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    main()