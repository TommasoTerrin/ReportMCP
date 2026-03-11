from google.adk.models import LiteLlm
from google.adk.agents import LlmAgent
from google.adk.sessions import Session

MY_API_KEY = "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"
URL= 'https://openrouter.ai/api/v1'
MODEL= "openrouter/google/gemma-3-4b-it:free" ## Specify the OpenRouter model using 'openrouter/' prefix

def test_model(api=MY_API_KEY, url:str=URL, model:str=MODEL):
    try:
        example_agent= LlmAgent(
            name="example_agent",
            model=LiteLlm(
                api_key=api,
                api_base=url,
                model=model,
            ),
            instruction="You are a helpful assistant.",
            description="An example agent that uses OpenRouter.",
        )
    except Exception as e:
        print(f"Error: {e}")

    return example_agent

test_model()


    
