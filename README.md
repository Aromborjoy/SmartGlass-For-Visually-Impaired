# Smart Glasses for the Visually Impaired
AI-powered smart glasses designed to assist visually impaired users through real-time object and color detection with voice feedback.

## Overview
This project was developed to help visually impaired individuals identify surrounding objects and colors in real time. The system uses Computer Vision and Artificial Intelligence techniques to analyze camera input and provide audio feedback through a speaker.

## Key Features
* Real-time Object Detection using YOLOv8
* Intelligent Color Recognition
* Voice Feedback System
* Bluetooth Audio Integration
* Adaptive Verification System
* Jetson Nano Deployment

## Technologies
* Python
* OpenCV
* YOLOv8
* ONNX Runtime
* Jetson Nano
* eSpeak-NG

## System Workflow
1. Capture image from camera
2. Detect objects using YOLOv8
3. Analyze object colors
4. Verify detection confidence
5. Generate voice feedback
6. Output result through Bluetooth speaker

## My Responsibilities
* Designed the overall system architecture
* Developed the object detection module
* Developed the color recognition algorithm
* Implemented voice feedback functionality
* Integrated Bluetooth audio devices
* Optimized deployment on Jetson Nano

## Challenges
One of the main challenges was improving color recognition accuracy under different lighting conditions. To address this issue, an adaptive verification mechanism and HSV-based color analysis were implemented to reduce false detections.

## Achievement
* Senior Project
* Developed a working AI-powered assistive device prototype
* Selected for the first round of NSC 2025
