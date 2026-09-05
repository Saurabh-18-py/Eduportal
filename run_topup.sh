#!/usr/bin/env bash
set -e

export DATABASE_URL="postgresql://postgres.uzzwxsedxovsuafoxoly:SaurabhxBatman17@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

export GROQ_API_KEYS="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,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,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,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,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"

python manage.py topup_questions --target 100 --batch-size 15 --difficulty hard
