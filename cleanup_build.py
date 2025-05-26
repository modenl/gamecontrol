#!/usr/bin/env python3
"""
Build cleanup utility
Cleans up processes and directories that might interfere with building
"""

import os
import sys
import time
import shutil
import psutil
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_and_kill_build_processes():
    """Find and terminate processes that might be using build directories"""
    logger.info("🔍 Searching for processes that might interfere with build...")
    
    target_processes = []
    build_dirs = ['build', 'dist']
    
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'cwd']):
        try:
            proc_info = proc.info
            should_kill = False
            reason = ""
            
            # Check if process is GameTimeLimiter
            if proc_info['name'] and 'GameTimeLimiter' in proc_info['name']:
                should_kill = True
                reason = "GameTimeLimiter executable"
            
            # Check if process executable is in build directories
            if proc_info['exe']:
                for build_dir in build_dirs:
                    if build_dir in proc_info['exe'] and os.getcwd().lower() in proc_info['exe'].lower():
                        should_kill = True
                        reason = f"executable in {build_dir} directory"
                        break
            
            # Check if process working directory is in build directories
            try:
                if proc_info['cwd']:
                    for build_dir in build_dirs:
                        build_path = os.path.join(os.getcwd(), build_dir)
                        if build_path.lower() in proc_info['cwd'].lower():
                            should_kill = True
                            reason = f"working directory in {build_dir}"
                            break
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            
            # Check command line for build directory references
            if proc_info['cmdline']:
                cmdline = ' '.join(proc_info['cmdline'])
                for build_dir in build_dirs:
                    if build_dir in cmdline and os.getcwd().lower() in cmdline.lower():
                        should_kill = True
                        reason = f"command line references {build_dir}"
                        break
            
            if should_kill:
                target_processes.append((proc, reason))
                
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    if not target_processes:
        logger.info("✅ No interfering processes found")
        return 0
    
    logger.info(f"🎯 Found {len(target_processes)} processes to terminate:")
    for proc, reason in target_processes:
        logger.info(f"   - {proc.info['name']} (PID: {proc.info['pid']}) - {reason}")
    
    # Terminate processes
    terminated_count = 0
    for proc, reason in target_processes:
        try:
            logger.info(f"🔪 Terminating {proc.info['name']} (PID: {proc.info['pid']})")
            proc.terminate()
            terminated_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"⚠️ Could not terminate {proc.info['name']}: {e}")
    
    if terminated_count > 0:
        logger.info(f"⏳ Waiting for {terminated_count} processes to terminate...")
        time.sleep(3)
        
        # Check if any processes are still running and force kill if necessary
        still_running = []
        for proc, reason in target_processes:
            try:
                if proc.is_running():
                    still_running.append(proc)
            except psutil.NoSuchProcess:
                pass
        
        if still_running:
            logger.warning(f"💀 Force killing {len(still_running)} stubborn processes...")
            for proc in still_running:
                try:
                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            time.sleep(1)
    
    return terminated_count

def safe_remove_directory(path, max_retries=3):
    """Safely remove a directory with retries"""
    if not os.path.exists(path):
        logger.info(f"📁 Directory {path} does not exist, skipping")
        return True
    
    logger.info(f"🗑️ Removing directory: {path}")
    
    for attempt in range(max_retries):
        try:
            shutil.rmtree(path)
            logger.info(f"✅ Successfully removed {path}")
            return True
            
        except PermissionError as e:
            logger.warning(f"⚠️ Attempt {attempt + 1}/{max_retries}: Permission denied - {e}")
            
            if attempt < max_retries - 1:
                # Try to change permissions
                try:
                    logger.info("🔧 Attempting to fix permissions...")
                    for root, dirs, files in os.walk(path):
                        for file in files:
                            try:
                                os.chmod(os.path.join(root, file), 0o777)
                            except:
                                pass
                        for dir in dirs:
                            try:
                                os.chmod(os.path.join(root, dir), 0o777)
                            except:
                                pass
                except Exception as perm_e:
                    logger.warning(f"Could not fix permissions: {perm_e}")
                
                wait_time = 2 * (attempt + 1)
                logger.info(f"⏳ Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"❌ Failed to remove {path} after {max_retries} attempts")
                return False
                
        except Exception as e:
            logger.error(f"❌ Unexpected error removing {path}: {e}")
            if attempt == max_retries - 1:
                return False
            time.sleep(1)
    
    return False

def cleanup_build_directories():
    """Clean up build and dist directories"""
    logger.info("🧹 Cleaning up build directories...")
    
    directories = ['build', 'dist']
    success = True
    
    for directory in directories:
        if not safe_remove_directory(directory):
            success = False
            logger.error(f"❌ Failed to remove {directory}")
        else:
            logger.info(f"✅ {directory} directory cleaned")
    
    return success

def main():
    """Main cleanup function"""
    logger.info("🚀 Starting build cleanup...")
    
    try:
        # Step 1: Kill interfering processes
        terminated_count = find_and_kill_build_processes()
        if terminated_count > 0:
            logger.info(f"✅ Terminated {terminated_count} processes")
        
        # Step 2: Clean up directories
        if cleanup_build_directories():
            logger.info("✅ Build directories cleaned successfully")
        else:
            logger.error("❌ Some directories could not be cleaned")
            logger.info("\n🔧 Manual steps you can try:")
            logger.info("1. Close any File Explorer windows showing build/dist folders")
            logger.info("2. Close any text editors with files from build/dist open")
            logger.info("3. Run this script as Administrator")
            logger.info("4. Restart your computer if the issue persists")
            return 1
        
        logger.info("🎉 Build cleanup completed successfully!")
        logger.info("💡 You can now run: python build.py")
        return 0
        
    except KeyboardInterrupt:
        logger.info("❌ Cleanup interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 