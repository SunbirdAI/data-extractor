---
title: 'ACRES: Center For Rapid Evidence Synthesis'
emoji: 👁
colorFrom: gray
colorTo: pink
sdk: gradio
sdk_version: 4.42.0
app_file: app.py
pinned: false
license: apache-2.0
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference


# ACRES RAG Project

## Project Setup

To test and run the project locally. Clone the project from github and change directoory to `acres`.

```sh
git clone https://github.com/SunbirdAI/acres.git
cd acres
```

Create python virtual environment and activate it.

```sh
python -m venv env
source env/bin/activate
```

Install project dependencies

```sh
pip install -r requirements.txt
```

## Run project locally
To test the project locally follow the steps below.

Copy `.env.example` to `.env` and provide the correct enviroment variable values.

```sh
cp .env.example .env
```

Run the application

```sh
python app.py
```

OR

```sh
gradio app.py
```

Browse the application with the link `http://localhost:7860/`


## Run with docker
To run the application with docker locally, first make sure you have docker installed. See [link](https://docs.docker.com/)

Build the project docker image

```sh
docker build -f Dockerfile.gradio -t gradio-app .
```

Create docker network

```sh
docker network create gradio-fastapi-network
```

Run the docker container 

```sh
docker run -it -p 7860:7860 --rm --name gradio --network=gradio-fastapi-network gradio-app
```

Browse the application with the link `http://localhost:7860/`


## Deploy to AWS ECS (Elastic Container Service) with Fargate

Install and configure the AWS CLI and aws credentials. See [link](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html)

OR: See the pdf document [here](https://docs.aws.amazon.com/pdfs/cli/latest/userguide/aws-cli.pdf#getting-started-quickstart)

Now follow the steps below to deploy to AWS ECS

Setup the default region and your aws account id

```sh
export AWS_DEFAULT_REGION=region # i.e us-east-1, eu-west-1
export AWS_ACCOUNT_ID=aws_account_id # ie. 2243838xxxxxx
```

Login into the AWS ECR (Elastic Container Registry) via the commandline

```sh
aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
```

Create a python image and push to ECR. This image will be used as the base image for the application image deployed on AWS ECS.

- Create python repository

```sh
aws ecr create-repository \
  --repository-name gradio-python \
  --image-tag-mutability MUTABLE
```

```sh
export ECR_PYTHON_URL="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/gradio-python"
echo $ECR_PYTHON_URL
```

- Pull python image and tag it to the ECR url

```sh
docker pull python:3.11.10-slim
docker tag python:3.11.10-slim $ECR_PYTHON_URL:3.11.10-slim

docker push $ECR_PYTHON_URL:3.11.10-slim
```

- Now create application repostory

```sh
aws ecr create-repository \
  --repository-name gradio-app-prod \
  --image-tag-mutability MUTABLE

export ECR_BACKEND_GRADIO_URL="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/gradio-app-prod"
echo $ECR_BACKEND_GRADIO_URL
```

- Build the docker image for the production and push to ECR

```sh
docker build --build-arg AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID -f Dockerfile.gradio.prod -t gradio-app-prod .
docker tag gradio-app-prod:latest "${ECR_BACKEND_GRADIO_URL}:latest"
docker push "${ECR_BACKEND_GRADIO_URL}:latest"
```

### Setup and Provision AWS ECS infra using AWS Cloudformation (IaC)

#### Install
To install the CFN-CLI run the command below

```sh
pip install cloudformation-cli cloudformation-cli-java-plugin cloudformation-cli-go-plugin cloudformation-cli-python-plugin cloudformation-cli-typescript-plugin
```

#### CFN-Toml

```sh
gem install cfn-toml
```


Copy `infra/ecs_config.template` to `infra/ecs_config.toml` and provide the correct `AWS Account ID` for the `ContainerImageGradio`

```sh
cp infra/ecs_config.template infra/ecs_config.toml
```


#### Deploy

To deploy the ECS infra run the commands below. It provisions the cloudformation stack changeset for review. 

Log into your aws console and search for `cloudformation`. See and review the changeset. If everything is good execute the changeset to finish with the infra deployment.

Then look for the outputs to the link for the deployed application.

```sh
chmod u+x bin/cfn/*
./bin/cfn/ecs-deploy
```
