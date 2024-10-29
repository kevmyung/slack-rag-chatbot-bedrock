import json
import boto3 
import requests
import os

KNOWLEDGE_BASE_ID = os.environ['KNOWLEDGE_BASE_ID']
REGION_NAME = os.environ['REGION_NAME']
MODEL_ID = os.environ['MODEL_ID']

def context_retrieval_from_kb(prompt, k=10):
    if not prompt:
        return []

    search_type='SEMANTIC'
    bedrock_agent_client = boto3.client('bedrock-agent-runtime', region_name=REGION_NAME)

    response = bedrock_agent_client.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalConfiguration={
            'vectorSearchConfiguration': {
                'numberOfResults': k,
                'overrideSearchType': search_type
            }
        },
        retrievalQuery={
            'text': prompt
        }
    )        
    raw_result = response.get('retrievalResults', [])

    if not raw_result:
        return []

    search_result = []
    for idx, result in enumerate(raw_result):
        content = result.get('content', {}).get('text', 'No content available')
        score = result.get('score', 'N/A')
        source = result.get('location', {})

        search_result.append({
            "index": idx + 1,
            "content": content,
            "source": source,
            "score": score
        })

    return search_result

def generate_response(question, context_results, user_id=None):
    if not context_results:
        return "No relevant documents found. Please try another question."

    context_text = ""
    for item in context_results:
        context_text += f"Content: {item['content']}\nSource: {item['source']}\n\n"

    system_prompt = "Please answer the question based on the following information. If information is not provided in the Source, please politely indicate that you don't know."

    bedrock_runtime = boto3.client('bedrock-runtime', region_name=REGION_NAME)

    try:
        response = bedrock_runtime.converse(
            modelId=MODEL_ID,
            system=[{'text': system_prompt}],
            messages=[
                {
                    'role': 'user',
                    'content': [
                        {
                            'text': f"Context:\n{context_text}\n\nQuestion: {question}"
                        }
                    ]
                }
            ],
            inferenceConfig={
                'maxTokens': 2000,
                'temperature': 0.7,
                'topP': 0.8,
            }
        )

        # Parse response
        answer = response['output']['message']['content'][0]['text']
        return answer

    except Exception as e:
        print(f"Error in generate_response: {str(e)}")
        return "Sorry, an error occurred while generating the response. Please try again later."

def format_context_for_slack(context_results):
    formatted_result = ""
    for item in context_results:
        formatted_result += f"*Reference Document {item['index']}*\n"
        formatted_result += f"Content: {item['content']}\n"
        formatted_result += f"Source: {item['source']}\n"
        formatted_result += f"Relevance: {item['score']}\n\n"
    return formatted_result

def lambda_handler(event, context):
    try:
        question = event['question']
        response_url = event['response_url']
        user_id = event['user_id']

        # Search context
        search_result = context_retrieval_from_kb(question, k=10)

        # Generate response
        answer = generate_response(question, search_result, user_id)
        print("answer:", answer)

        # Format context
        formatted_context = format_context_for_slack(search_result)

        # Send final response
        final_response = {
            'response_type': 'in_channel',
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f'*<@{user_id}>\'s Question:*\n>{question}'
                    }
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f'*Answer:*\n{answer}'
                    }
                },
                {
                    'type': 'divider'
                }
            ]
        }

        response = requests.post(response_url, json=final_response)
        if response.status_code != 200:
            print(f"Error sending final response: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"Error in async processing: {str(e)}")
        error_response = {
            'response_type': 'ephemeral',
            'text': f'Sorry, an error occurred during processing: {str(e)}'
        }
        requests.post(response_url, json=error_response)