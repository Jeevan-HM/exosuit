import multiprocessing
import subprocess

def run_script(script_path):
    subprocess.call(['python3', script_path])

if __name__ == '__main__':
    script_paths = ['simulate_shoes_left.py','simulate_shoes_right.py','simulate_shoes_left.py', 'simulate_emg.py', 'simulate_imu.py']  # Replace with the paths to your scripts
    # script_paths = ['simulate_shoes_left.py','simulate_shoes_right.py']
    
    processes = []
    for script_path in script_paths:
        p = multiprocessing.Process(target=run_script, args=(script_path,))
        processes.append(p)
        p.start()

    # Wait for all processes to finish
    for p in processes:
        p.join()
