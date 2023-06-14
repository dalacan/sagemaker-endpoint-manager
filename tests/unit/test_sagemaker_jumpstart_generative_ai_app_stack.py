import aws_cdk as core
import aws_cdk.assertions as assertions

from sagemaker_jumpstart_generative_ai_app.sagemaker_jumpstart_generative_ai_app_stack import SagemakerJumpstartGenerativeAiAppStack

# example tests. To run these tests, uncomment this file along with the example
# resource in sagemaker_jumpstart_generative_ai_app/sagemaker_jumpstart_generative_ai_app_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = SagemakerJumpstartGenerativeAiAppStack(app, "sagemaker-jumpstart-generative-ai-app")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
