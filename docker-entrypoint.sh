#!/bin/bash
# Starte RabbitMQ im Hintergrund
sudo service rabbitmq-server start

# Starte die Python-Anwendung
exec python start.py