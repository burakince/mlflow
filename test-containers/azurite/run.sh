#!/bin/sh

wait_for() {
  echo "Waiting for $1 to listen on $2...";
  while ! nc -z $1 $2;
  do
    echo "Sleeping. Waiting for $1 to listen on $2...";
    sleep 2;
  done
}

# Azurite Blob service
wait_for localhost 10000

# Azurite Queue service
wait_for localhost 10001

# Azurite Table service
wait_for localhost 10002

node /create-container.js
