#!/usr/bin/env python3
"""
Example script demonstrating how to use modal-ssh with a custom image.
"""

import modal
from modal import Image, App
from pathlib import Path

from modal_ssh import configure_ssh_image, maybe_upload_project, ssh_function_wrapper

# Create a custom image with additional dependencies
base_image = Image.debian_slim(python_version="3.10").pip_install(
    "numpy",
    "pandas"
)

# Configure the image for SSH
base_image.add_local_python_source("modal_ssh")
ssh_image = configure_ssh_image(base_image=base_image)

# Create a Modal app
app = App(name="custom-ssh-example")

vol = modal.Volume.from_name("ssh-test", create_if_missing=True)
@app.function(
    gpu="A10G",
    timeout=60*60*4,  # 4 hour timeout
    image=ssh_image,
    volumes={
        "/root/data": vol,  # Changed to /root/data to be consistent with CLI
    }
)
def ssh_function():
    ssh_function_wrapper()

@app.local_entrypoint()
def main():
    # Upload the project files first
    project_dir = str(Path.cwd())  # Current working directory
    project_name = Path(project_dir).name  # Name of the directory
    
    print(f"Uploading project from {project_dir} as {project_name}...")
    maybe_upload_project(
        volume=vol,
        project_dir_name=project_name,
        from_path=project_dir,
        force_reupload=True
    )
    
    # Then start the SSH server
    print("Starting SSH server...")
    ssh_function.remote() 