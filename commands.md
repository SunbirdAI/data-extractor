docker network create gradio-fastapi-network

docker run -it -p 7860:7860 --rm --name gradio --network=gradio-fastapi-network gradio-app

docker run -it -p 7860:7860 --rm --name gradio --network=gradio-fastapi-network gradio-app-prod


export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCOUNT_ID=2244276xxxxx
aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com"

aws ecr create-repository \
  --repository-name gradio-python \
  --image-tag-mutability MUTABLE

export ECR_PYTHON_URL="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/gradio-python"
echo $ECR_PYTHON_URL

docker pull python:3.11.10-slim
docker tag python:3.11.10-slim $ECR_PYTHON_URL:3.11.10-slim

docker push $ECR_PYTHON_URL:3.11.10-slim


aws ecr create-repository \
  --repository-name gradio-app-prod \
  --image-tag-mutability MUTABLE

export ECR_BACKEND_GRADIO_URL="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/gradio-app-prod"
echo $ECR_BACKEND_GRADIO_URL

docker build --build-arg AWS_ACCOUNT_ID=2244276xxxxx -t your-image-name .
docker build -f Dockerfile.gradio.prod -t gradio-app-prod .

docker build --build-arg AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID -f Dockerfile.gradio.prod -t gradio-app-prod .
docker tag gradio-app-prod:latest "${ECR_BACKEND_GRADIO_URL}:latest"
docker push "${ECR_BACKEND_GRADIO_URL}:latest"


docker build -f Dockerfile.api -t fastapi-app .
docker run -it -p 8000:8000 --rm --name fastapi --network=gradio-fastapi-network fastapi-app

aws ecr create-repository \
  --repository-name fastapi-api-prod \
  --image-tag-mutability MUTABLE

export ECR_BACKEND_FASTAPI_URL="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/fastapi-api-prod"
echo $ECR_BACKEND_FASTAPI_URL

docker build --build-arg AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID -f Dockerfile.api.prod -t fastapi-api-prod .
docker tag fastapi-api-prod:latest "${ECR_BACKEND_FASTAPI_URL}:latest"
docker push "${ECR_BACKEND_FASTAPI_URL}:latest"

