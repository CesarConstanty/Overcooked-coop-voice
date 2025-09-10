#!/bin/bash

echo "Création des dossiers de données..."
mkdir -p data/{instance,trajectories,overcooked_ai_py/data/planners}

echo "Construction de l'image Docker..."
docker build -t overcooked:dev .

echo "Lancement de l'application..."
docker run -d \
  --name overcooked-app \
  -p 5000:5000 \
  -v $(pwd)/data/instance:/overcooked/instance \
  -v $(pwd)/data/trajectories:/overcooked/trajectories \
  -v $(pwd)/data/overcooked_ai_py/data/planners:/overcooked/overcooked_ai_py/data/planners \
  -e FLASK_ENV=production \
  --restart unless-stopped \

  overcooked:dev
