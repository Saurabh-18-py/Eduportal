#!/usr/bin/env bash
set -e

export DATABASE_URL="postgresql://postgres.uzzwxsedxovsuafoxoly:SaurabhxBatman17@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

# GROQ_API_KEY should already be in your ~/.bashrc. If not, uncomment and fill in:
# export GROQ_API_KEY="your-key-here"

python manage.py topup_questions --target 100 --batch-size 20 --difficulty hard
