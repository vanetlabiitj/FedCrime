# FedCrime: Federated Learning-based Crime Prediction

## Overview
Federated Learning-based Crime Prediction is a project aimed at predicting crime occurrences using a decentralized machine learning approach. By leveraging federated learning, this project ensures data privacy and security by keeping data localized on client devices, only sharing model updates with a central server.

## Features
- **Federated Learning**: Train models across multiple decentralized devices without sharing raw data.
- **Crime Prediction**: Predict various categories of crimes using historical data.
- **Privacy-Preserving**: Maintain user privacy by not transferring sensitive data to a central server.
- **Scalable Architecture**: Support for multiple clients and large datasets.

## Installation
To get started, clone the repository and install the necessary dependencies as follows:
flwr==1.0.0
torch==1.10.0
torchvision==0.11.1
numpy==1.21.2
pandas==1.3.3
scikit-learn==0.24.2
matplotlib==3.4.3
tqdm==4.62.3

## Directory structure
federated-crime-prediction/
├── datasets/                   # Dataset directory
├── baseline/                 # Saved models
├── main/                    # Source code
│   ├── main.py           # Federated server
├── utils                    # Helping functions
├── README.md               # Project README

## Running the code

main.py contain the code for the FedCrime.


************************************* This repository is under preparation*****************************************
