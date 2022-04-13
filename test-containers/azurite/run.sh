#!/bin/sh

wait_for() {
  echo "Waiting for $1 to listen on $2...";
  while ! nc -z $1 $2;
  do
    echo "Sleeping. Waiting for $1 to listen on $2...";
    sleep 2;
  done
}

wait_for localhost 10000
wait_for localhost 10001

node /create-container.js
