#!/usr/bin/env bash
set -e

sudo su

apt-get update
apt install -y git
apt install git-lfs -y
apt install python3-pip -y
git lfs install
apt install python3.12-venv -y

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
nohup ollama serve > /home/ubuntu/ollama.log 2>&1 &

# Wait for ollama to be ready
sleep 10

# Pull models as the ollama user
ollama pull deepseek-r1:8b
ollama pull gemma3
ollama pull qwen3:8b
ollama pull mxbai-embed-large
ollama pull nomic-embed-text

# Clone repository

git clone https://github.com/SunbirdAI/acres.git
cd acres
cp .env.example .env

# Install dependencies
python3 -m venv env
bash -c "source env/bin/activate && pip install --upgrade pip"
bash -c "source env/bin/activate && pip install -r requirements.txt"

# Start streamlit (run in background)
bash -c "cd /home/ubuntu/acres && source env/bin/activate && nohup gradio app.py > /var/log/gradio.log 2>&1 &"
bash -c "cd /home/ubuntu/acres && source env/bin/activate && nohup uvicorn api:app --host 0.0.0.0 --port 8000 > /var/log/fastapi-uvicorn.log 2>&1 &"


# Log completion
echo "Setup completed successfully at $(date)" >> /var/log/user-data.log