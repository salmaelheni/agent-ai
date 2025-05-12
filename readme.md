## Installation
Follow these instructions
 
```bash

py -3.11 -m venv venv # Use a python version 3.11
venv\Scripts\activate #Open venv
pip install -r requirements.txt # Install packages

```
in case the commmand 
```bash
venv\Scripts\activate #Open venv
```
did not work on powershell, use this
```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```
than repeat
```bash
venv\Scripts\activate #Open venv
```

## Run project

```bash

python main.py

```
