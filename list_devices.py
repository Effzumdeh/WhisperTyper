import sounddevice as sd

def list_devices():
    devices = sd.query_devices()
    print("Available Audio Devices:\n")
    host_apis = sd.query_hostapis()
    
    print(f"{'ID':<4} {'Name':<40} {'API':<15} {'In':<5} {'Out':<5}")
    print("-" * 75)
    
    for i, dev in enumerate(devices):
        # We only care about input devices (max_input_channels > 0)
        # But showing all helps debugging
        is_input = dev['max_input_channels'] > 0
        if is_input:
            api_name = host_apis[dev['hostapi']]['name']
            print(f"{i:<4} {dev['name']:<40} {api_name:<15} {dev['max_input_channels']:<5} {dev['max_output_channels']:<5}")

    print("\nDefault Input Device:")
    try:
        default_in = sd.query_devices(kind='input')
        print(f"Name: {default_in['name']}, ID: {default_in['index'] if 'index' in default_in else 'Unknown'}")
    except Exception as e:
        print(f"Error querying default device: {e}")

if __name__ == "__main__":
    list_devices()
