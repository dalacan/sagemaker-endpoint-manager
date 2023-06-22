
# Deploying a auto start/stop Amazon SageMaker Foundation Model endpoint backed by a API Gateway/Lambda

This demo code provides you with a template to develop an integration with an Amazon SageMaker foundation model fronted by a serverless API with a simple dynamodb authorizer using CDK.

The real-time endpoint also features a automatic start/stop functionality by setting an expiry datetime for the endpoint. Similar to a parking meter whereby you top up credits to ensure that your parking does not expire, in this case, you keep renewing the endpoint expiry date time to keep it running.

This simple solution was implemented to solve a recurring problem with users leaving their Amazon SageMaker endpoint on and forgetting to turn it off. One way of solving it is to implement a schedule, however having to constantly set a pre-defined datetime can be cumbersome as schedules can change. Instead by intentionally forcing the user to top up tokens can raise the awareness of the cost of the endpoint (particularly for LLM endpoint) and also ensure that the user is intentional in how much more time they need to use the endpoint for testing.

## To Do 
- [ ] Bug - if time is expired, extending the time will need to be greater than the different of current time + time required. Will need to add a check to see if time is expired, add time from now + time required. 

## How to deploy the stack

### 1. Create a python virtualenv

```
$ python3 -m venv .venv
```

### 2. Activate your virtual environment

For Mac/Linux platform:
```
$ source .venv/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```
### 3. Install required dependencies

```
$ pip install -r requirements.txt
```

### 4. Bootstrap your environment (if required)
If you have not previously used CDK, bootstrap your environment

```
$ cdk bootstrap
```

### 5. Define your configuration
Open the `app.py` and set your desired configurations

### 6.1 Deploy endpoint
If you want to deploy a real-time endpoint, follow steps 6.1.x, if not refer to step 6.2 for async endpoints. 
#### 6.1.1 Deploy the real-time model stack

Deploy the model stack. This will register the foundation model and endpoint configurations

```
$ cdk deploy FlanT5MeteredStack
```

#### 6.1.2 Deploy the endpoint manager stack
Deploy the lambda that will be responsible for the automatic creation and deletion of your Amazon SageMaker endpoint
```
$ cdk deploy EndpointManagerStack
```

#### 6.1.3 Deploy serverless API
Deploy the serverless API fronting the sagemaker endpoint and API
```
$ cdk deploy FlanT5LambdaStack && cdk deploy APIStack
```

#### 6.1.4 Setup your auth
In your AWS account, you will find a Dynamodb table `auth` which stores a token (or pass code) which you will use to as an authorization token to access the APIs. Create an item in the `auth` table with an attribute `token` and set the value to your pass code which you will use when calling the API.

#### 6.1.5 Querying endpoint uptime

To check the time left on your endpoint run the following:

```
curl --location 'https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/endpoint-expiry' \
--header 'Authorization: <YOUR TOKEN VALUE>'
```

Expected Response:
```
{
    "EndpointExpiry ": "22-06-2023-08-24-12",
    "TimeLeft": "00:00:10.21130"
}
```

#### 6.1.5 Querying endpoint uptime

To extend the amount of time your endpoint will be kept alive, run the following:

```
curl --location 'https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/endpoint-expiry' \
--header 'Authorization: <YOUR TOKEN VALUE>' \
--header 'Content-Type: application/json' \
--data '{
    "minutes": 10
}'
```

Expected Response:
```
{
    "EndpointExpiry ": "22-06-2023-08-24-12",
    "TimeLeft": "00:00:10.21130"
}
```

#### 6.1.6 Testing model API endpoint
To run inference against the SageMaker endpoint via the API gateway, run the following:

```
curl --location 'https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/flan' \
--header 'Authorization: <YOUR TOKEN VALUE>' \
--header 'Content-Type: application/json' \
--data '{
    "text_inputs":"write a story about beautiful weather on a topical island.", 
    "max_length": 50, 
    "temperature": 0.0,
    "seed": 321
}'
```

Expected response
```
{
    "generated_texts": [
        "..."
    ]
}
```

#### 6.2 Deploy async endpoint stack
If you'd like to deploy an aynchrnonous foundational model endpoint, follow this step. (Note this does not have use the endpoint manager feature for auto start/stop)
```
cdk deploy FlanT5AsyncStack
```

## How does the endpoint manager work?

1. When the stack is provisioned for the first time, the user defined the initial required endpoint provision time in minutes (`initial_provision_time_minutes`) in the `app.py`
2. Once provisioned, a start/stop lambda will poll an Amazon SageMaker Parameter store parameter to check the expiry date/time. If the date/time is not expired, the lambda will create the model endpoint if it has not been created.
3. If the expiry datetime is less than the current time, the lambda will automatically delete the endpoint.
4. Users can check the time left on their endpoint by querying the `endpoint-expiry` API (https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/endpoint-expiry)
5. Users can also extend the endpoint uptime by sending a request to the `endpoint-expiry` API by providing the time in minutes the request body. Example below:
```
{
    "minutes": 10
}
```
## Code Structure


Enjoy!

## References

Building an API Gateway with CDK - https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_apigateway/README.html#lambda-based-request-authorizer

