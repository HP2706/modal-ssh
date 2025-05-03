from modal import Image, App, Volume
import modal
import os
from typing import Optional
import subprocess
import time
import signal
import atexit
from typing import List
import fnmatch


def maybe_upload_project(
    volume : Optional[Volume] = None,
    project_dir_name : Optional[str] = None, # default to name of parent dir
    from_path : Optional[str] = None,
    force_reupload : bool = False,
    ignore_patterns : Optional[List[str]] = ['.venv', 'triton', '*/triton', '*.venv'],
) -> None:
    if project_dir_name is None:
        project_dir_name = str(os.path.basename(os.getcwd()))
    if from_path is None:
        from_path = os.getcwd()
        
    if volume is None:
        print("creating a new volume 'ssh-volume'")
        volume = Volume.from_name('ssh-volume')

    if project_dir_name in [x.path for x in volume.listdir('')] and not force_reupload:
        print("project already exists")
        return
    
    elif force_reupload:
        print("force reupload")
    else:
        print("no data folder", volume.listdir(''))
    
    with volume.batch_upload(force=force_reupload) as uploader:
        for f in os.listdir(from_path):
            last_name = os.path.basename(f)
            if ignore_patterns is not None and any(fnmatch.fnmatch(last_name, pattern) for pattern in ignore_patterns):
                print("ignoring", f)
                continue
            
            if os.path.isdir(f):
                print("uploading directory", f, "to", os.path.join(project_dir_name, last_name))
                uploader.put_directory(
                    os.path.join(from_path, f),
                    remote_path=os.path.join(project_dir_name, last_name),
                )
            else:
                print("uploading file", f, "to", os.path.join(project_dir_name, last_name))
                uploader.put_file(
                    os.path.join(from_path, f),
                    remote_path=os.path.join(project_dir_name, last_name),
                )
    


def configure_ssh_image(base_image : Optional[Image] = None):
    """
    Configure a Modal image with SSH server and other dependencies.
    
    Args:
        base_image: Optional base Modal image to extend. If None, uses debian_slim with Python 3.10.
        
    Returns:
        A Modal image configured with SSH server.
    """
    if base_image is None:
        base_image = Image.debian_slim(python_version="3.10")
    
    return base_image.apt_install(
        "openssh-server",
        "git"
    ).run_commands(
        "mkdir -p /run/sshd",
    ).env(
        {
            "PATH": "/usr/local/bin:$PATH",
        }
    ).add_local_file(
        os.path.expanduser("~/.ssh/id_rsa.pub"), 
        "/root/.ssh/authorized_keys",
        copy=True
    ).env(
        {
            "GIT_USER_NAME": os.environ.get("GIT_USER_NAME", "Default Name"),
            "GIT_USER_EMAIL": os.environ.get("GIT_USER_EMAIL", "default@example.com")
        }
    )

def ssh_function_wrapper():
    """
    Wrapper function that sets up and runs an SSH server in a Modal container.
    """
    def cleanup(signum=None, frame=None):
        try:
            # Graceful process termination
            os.system('pkill -15 -f python')  # Send SIGTERM first
            time.sleep(2)  # Give processes time to cleanup
            current_pid = os.getpid()
            os.system(f'pkill -9 -f python && kill -9 $(pgrep -f python | grep -v {current_pid})')
        except Exception as e:
            print(f"Cleanup error: {e}")

    # Register cleanup for various signals and exit
    signal.signal(signal.SIGHUP, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    atexit.register(cleanup)

    # Configure sshd with custom settings
    sshd_config = """
    PrintMotd no
    PrintLastLog no
    UsePAM no
    """
    with open("/etc/ssh/sshd_config.d/custom.conf", "w") as f:
        f.write(sshd_config)

    try:
        subprocess.run(["service", "ssh", "restart"], check=True)
        with modal.forward(port=22, unencrypted=True) as tunnel:
            hostname, port = tunnel.tcp_socket
            connection_cmd = f'ssh -p {port} root@{hostname}'
            print(f"SSH into container using: {connection_cmd}")
            
            while True:
                time.sleep(60)  # Check every minute
                # Verify SSH daemon is still running
                try:
                    subprocess.run(["pgrep", "sshd"], check=True)
                except subprocess.CalledProcessError:
                    print("SSH daemon died, restarting...")
                    subprocess.run(["service", "ssh", "restart"], check=True)
    except Exception as e:
        print(f"SSH server error: {e}")
    finally:
        cleanup()


# Define a global SSH function that will be decorated dynamically
def _ssh_function():
    """Global SSH function that will be decorated by app.function."""
    ssh_function_wrapper()

def create_ssh_function(
    app: App,
    volume: Optional[Volume] = None,
    **kwargs
):
    """
    Create a Modal function that runs an SSH server.
    
    Args:
        app: Modal App instance
        volume: Optional Modal Volume instance
        **kwargs: Additional arguments to pass to app.function
        
    Returns:
        A Modal function that runs an SSH server
    """
    # Create a wrapper function that applies the decorator to the global function
    # This avoids the issue of trying to decorate a function defined inside another function
    
    # First, prepare all the kwargs
    function_kwargs = kwargs.copy()
    
    # If volume is provided, ensure it's included in the volumes dict
    if volume is not None:
        if 'volumes' not in function_kwargs:
            function_kwargs['volumes'] = {}
        function_kwargs['volumes']['/root/data'] = volume
    
    # Apply the decorator to the global function and return it
    return app.function(**function_kwargs)(_ssh_function)

