#!/bin/bash

echo "Création des dossiers de données..."
mkdir -p data/{instance,trajectories,overcooked_ai_py/data/planners}

echo "Construction de l'image Docker..."
docker-compose build

echo "Lancement de l'application..."
docker-compose up -d

