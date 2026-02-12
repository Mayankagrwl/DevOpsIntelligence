
import os
import json
import sys

# Add current directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp_client import K8sNativeClient
except ImportError as e:
    print(f"ImportError: {e}")
    print("Ensure you are running this from the correct directory.")
    sys.exit(1)

def verify_troubleshoot_tools():
    print("Initializing K8sNativeClient...")
    client = K8sNativeClient()
    
    if not client.initialized:
        print("Failed to initialize K8s client. Check kubeconfig.")
        return

    namespace = "default"
    # unique name to avoid conflicts
    import uuid
    pod_name = f"test-troubleshoot-{str(uuid.uuid4())[:8]}"
    image = "nginx:alpine"

    print(f"\n1. Creating pod '{pod_name}' using create_pod...")
    try:
        res = client.create_pod(pod_name, image, namespace=namespace)
        print(f"Create Result: {json.dumps(res, indent=2)}")
    except Exception as e:
        print(f"Error creating pod: {e}")

    print(f"\n2. Describing pod '{pod_name}' using get_pod_details...")
    import time
    time.sleep(2) # Wait a bit for pod to be created
    try:
        res = client.get_pod_details(pod_name, namespace=namespace)
        # Just print name and status to keep output short
        summary = {"name": res.get("name"), "status": res.get("status")}
        print(f"Describe Summary: {json.dumps(summary, indent=2)}")
    except Exception as e:
        print(f"Error describing pod: {e}")

    print(f"\n3. Deleting pod '{pod_name}' using delete_resource...")
    try:
        res = client.delete_resource("pod", pod_name, namespace=namespace)
        print(f"Delete Result: {json.dumps(res, indent=2)}")
    except Exception as e:
        print(f"Error deleting pod: {e}")

if __name__ == "__main__":
    verify_troubleshoot_tools()
