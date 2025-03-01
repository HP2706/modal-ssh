# Modal SSH

A simple Python package for SSH-ing into a Modal container.

## Installation

```bash
pip install modal-ssh
```

Or install from source:

```bash
git clone https://github.com/yourusername/modal-ssh.git
cd modal-ssh
pip install -e .
```

For development, install with pytest:

```bash
pip install -e ".[dev]"
```

## Prerequisites

1. You need to have Modal CLI set up and authenticated
2. You need to have SSH keys set up on your local machine

## Usage

### Custom Image Example

```python
import modal
from modal import App, Image, Volume
from modal_ssh import configure_ssh_image, ssh_function_wrapper

# Create a Modal app
app = App(name="my-ssh-app")

# Create a custom image with additional dependencies
base_image = Image.debian_slim(python_version="3.10").pip_install(
    "numpy",
    "pandas",
    "scikit-learn"
)
ssh_image = configure_ssh_image(base_image=base_image)
volume = Volume.from_name("ssh-volume", create_if_missing=True)

@app.function(
    gpu="A10G",
    timeout=14400,
    image=ssh_image,
    volumes={
        "/root/entry": volume
    }
)
def ssh_function():
    ssh_function_wrapper()
```

## License

MIT 