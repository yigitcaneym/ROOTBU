import platform
import subprocess

BASH_SCRIPT = """
#!/bin/bash
set -e

# Ensure PATH has conda just in case it was installed previously but not loaded
export PATH="$HOME/miniconda3/bin:$PATH"

echo "Starting ROOT setup in Linux/WSL environment..."

# Check if conda exists
if ! command -v conda &> /dev/null
then
    echo "Downloading Miniconda..."
    mkdir -p ~/miniconda3
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
    echo "Installing Miniconda..."
    bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
    rm -rf ~/miniconda3/miniconda.sh
    
    echo "Initializing conda..."
    ~/miniconda3/bin/conda init bash
    ~/miniconda3/bin/conda init zsh
    
    # Reload bashrc to use conda immediately
    export PATH="$HOME/miniconda3/bin:$PATH"
    echo "Miniconda installed successfully."
else
    echo "Conda is already installed."
fi

# Activate conda
echo "Activating conda base environment..."
eval "$(conda shell.bash hook)"

echo "Setting strict channel priority..."
conda config --set channel_priority strict

# Check if environment exists
if conda env list | grep -q "root_env"; then
    echo "Environment root_env already exists."
else
    echo "Creating root_env with ROOT... This may take a while to download and extract."
    conda create -y -n root_env -c conda-forge root
fi

conda activate root_env
conda config --env --add channels conda-forge

# Modify .bashrc
if ! grep -q "conda activate root_env" ~/.bashrc; then
    echo "Appending conda environment activation to .bashrc..."
    echo -e "\n# Added by ROOT Setup App\nconda activate root_env\nroot" >> ~/.bashrc
    echo ".bashrc updated with root startup commands."
else
    echo ".bashrc already contains the activation command."
fi

echo "ROOT System Setup completed successfully! Open your Ubuntu/WSL terminal to start using it."
"""

def run_installation():
    sys_name = platform.system()
    
    if sys_name == "Windows":
        yield "Detected Windows OS. Checking for WSL..."
        
        try:
            # Check for wsl availability
            wsl_check = subprocess.run(
                ["wsl", "--status"], 
                capture_output=True, 
                text=True, 
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        except Exception:
            # if wsl fails entirely, run simple wsl string
            wsl_check = None
            
        # Try a quick --help to see if wsl works
        try:
            wsl_help = subprocess.run(
                ["wsl", "--help"], 
                capture_output=True, 
                text=True, 
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if wsl_help.returncode != 0:
                raise FileNotFoundError()
        except FileNotFoundError:
            yield "WSL executable not found or not properly configured."
            yield "Please run 'wsl --install' in a command prompt or PowerShell as Administrator."
            return

        yield "WSL detected. Proceeding to run installation script within WSL..."
        yield "--------------------------------------------------------"
        
        process = subprocess.Popen(
            ["wsl", "bash", "-c", BASH_SCRIPT], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1, 
            universal_newlines=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        
        if process.stdout:
            for line in iter(process.stdout.readline, ""):
                if line:
                    yield line.strip()
                    
            process.stdout.close()
        process.wait()

        if process.returncode == 0:
            yield "--------------------------------------------------------"
            yield "Finished Successfully!"
        else:
            yield "--------------------------------------------------------"
            yield f"Process exited with code {process.returncode}."

    elif sys_name == "Linux" or sys_name == "Darwin": # Testing on Darwin for Mac
        yield f"Detected OS: {sys_name}."
        yield "Executing native bash installation script..."
        yield "--------------------------------------------------------"
        
        # for darwin just mock the sleep to see the UI working, although we'll allow standard linux flow
        if sys_name == "Darwin":
            yield "[macOS Detected: Mocking execution for rapid development check]"
            mock_script = "echo 'Starting ROOT setup...'; sleep 1; echo 'Downloading Miniconda...'; sleep 1; echo 'Finished!'"
            process = subprocess.Popen(["bash", "-c", mock_script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
        else:
            process = subprocess.Popen(["bash", "-c", BASH_SCRIPT], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
            
        if process.stdout:
            for line in iter(process.stdout.readline, ""):
                if line:
                    yield line.strip()
                    
            process.stdout.close()
        process.wait()
        
        if process.returncode == 0:
            yield "--------------------------------------------------------"
            yield "Finished Successfully!"
        else:
            yield "--------------------------------------------------------"
            yield f"Process exited with code {process.returncode}."
            
    else:
        yield f"Unsupported Operating System: {sys_name}"
