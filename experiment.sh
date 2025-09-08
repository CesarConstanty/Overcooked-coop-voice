#!/bin/bash

# --- Configuration ---
URL="http://localhost:5000/?TEST_UID="
CONF="&CONFIG=overcooked_test_recipe_mechanic"

BROWSER="firefox"       

# --- Script ---
echo "Attempting to launch 50 tabs of: $URL using $BROWSER simultaneously."

for i in {1..10}; do
    "$BROWSER" -new-tab "$URL""$i""$CONF" &
    echo "$BROWSER" -new-tab "$URL""$i""$CONF"
done

echo "Launch sequence completed for 10 tabs."