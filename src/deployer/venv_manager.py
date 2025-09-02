import os
import subprocess
import venv
import logging
from pathlib import Path

logger = logging.getLogger('deployer')


class VenvManager:
    """Manage Python virtual environments"""
    
    def create(self, venv_path, python_version=None):
        """Create a new virtual environment"""
        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(venv_path), exist_ok=True)
            
            if python_version:
                # Try to use specific Python version
                python_exe = f"python{python_version}"
                try:
                    # Check if specific version exists
                    subprocess.run([python_exe, '--version'], check=True, capture_output=True)
                    # Create venv with specific Python version
                    subprocess.run([python_exe, '-m', 'venv', venv_path], check=True)
                    logger.info(f"Created virtual environment at {venv_path} with Python {python_version}")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Try without patch version (e.g., python3.11 -> python3)
                    try:
                        major_version = '.'.join(python_version.split('.')[:1])
                        python_exe = f"python{major_version}"
                        subprocess.run([python_exe, '--version'], check=True, capture_output=True)
                        subprocess.run([python_exe, '-m', 'venv', venv_path], check=True)
                        logger.warning(f"Python {python_version} not found, using Python {major_version}")
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        # Fall back to default Python
                        logger.warning(f"Python {python_version} not found, using default Python 3")
                        subprocess.run(['python3', '-m', 'venv', venv_path], check=True)
            else:
                # Use default Python 3
                subprocess.run(['python3', '-m', 'venv', venv_path], check=True)
                logger.info(f"Created virtual environment at {venv_path}")
            
            # Upgrade pip
            self.run_pip(venv_path, ['install', '--upgrade', 'pip'])
            
        except Exception as e:
            logger.error(f"Failed to create virtual environment: {str(e)}")
            raise
    
    def install_requirements(self, venv_path, requirements_file):
        """Install requirements in virtual environment"""
        try:
            if not os.path.exists(requirements_file):
                raise FileNotFoundError(f"Requirements file not found: {requirements_file}")
            
            logger.info(f"Installing requirements from {requirements_file}")
            self.run_pip(venv_path, ['install', '-r', requirements_file])
            logger.info("Requirements installed successfully")
            
        except Exception as e:
            logger.error(f"Failed to install requirements: {str(e)}")
            raise
    
    def install_package(self, venv_path, package):
        """Install a single package"""
        try:
            logger.info(f"Installing package {package}")
            self.run_pip(venv_path, ['install', package])
            logger.info(f"Package {package} installed successfully")
            
        except Exception as e:
            logger.error(f"Failed to install package {package}: {str(e)}")
            raise
    
    def run_pip(self, venv_path, args):
        """Run pip command in virtual environment"""
        pip_path = os.path.join(venv_path, 'bin', 'pip')
        
        if not os.path.exists(pip_path):
            raise FileNotFoundError(f"Pip not found in virtual environment: {venv_path}")
        
        cmd = [pip_path] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=600  # 10 minute timeout for pip operations
            )
            
            if result.stdout:
                logger.debug(f"Pip output: {result.stdout}")
            
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Pip command failed: {e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            logger.error("Pip command timed out")
            raise
    
    def run_python(self, venv_path, args, cwd=None, env=None):
        """Run Python command in virtual environment"""
        python_path = os.path.join(venv_path, 'bin', 'python')
        
        if not os.path.exists(python_path):
            raise FileNotFoundError(f"Python not found in virtual environment: {venv_path}")
        
        cmd = [python_path] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=cwd,
                env=env,
                timeout=300  # 5 minute timeout
            )
            
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Python command failed: {e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            logger.error("Python command timed out")
            raise
    
    def get_installed_packages(self, venv_path):
        """Get list of installed packages"""
        try:
            output = self.run_pip(venv_path, ['list', '--format=json'])
            import json
            return json.loads(output)
        except Exception as e:
            logger.error(f"Failed to get installed packages: {str(e)}")
            return []
    
    def freeze_requirements(self, venv_path, output_file):
        """Freeze current requirements to file"""
        try:
            output = self.run_pip(venv_path, ['freeze'])
            with open(output_file, 'w') as f:
                f.write(output)
            logger.info(f"Froze requirements to {output_file}")
        except Exception as e:
            logger.error(f"Failed to freeze requirements: {str(e)}")
            raise
    
    def delete(self, venv_path):
        """Delete virtual environment"""
        try:
            if os.path.exists(venv_path):
                import shutil
                shutil.rmtree(venv_path)
                logger.info(f"Deleted virtual environment at {venv_path}")
        except Exception as e:
            logger.error(f"Failed to delete virtual environment: {str(e)}")
            raise