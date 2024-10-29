import json
import boto3
from urllib import parse

def lambda_handler(event, context):
    try:
        body = event.get('body', '')
        params = dict(parse.parse_qs(body))
        question = params.get('text', [''])[0]
        response_url = params.get('response_url', [''])[0]
        user_id = params.get('user_id', [''])[0]

        # Invoke second Lambda function asynchronously
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName='slack-async-processor',  # Second Lambda function name
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps({
                'question': question,
                'response_url': response_url,
                'user_id': user_id
            })
        )

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'response_type': 'in_channel',
                'text': f'Processing <@{user_id}>\'s question... Please wait a moment.'
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'response_type': 'ephemeral',
                'text': 'Sorry, an error has occurred.'
            })
        }