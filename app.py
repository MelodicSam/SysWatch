from flask import Flask, jsonify, render_template
import psutil
import platform
import socket
import time
from datetime import datetime, timedelta

app = Flask(__name__)

def bytes_to_human(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

def uptime_str():
    seconds = int(time.time() - psutil.boot_time())
    td = timedelta(seconds=seconds)
    return f"{td.days}d {td.seconds//3600}h {(td.seconds%3600)//60}m"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/system")
def system_info():
    uname = platform.uname()
    return jsonify({
        "hostname":    socket.gethostname(),
        "os":          f"{uname.system} {uname.release}",
        "arch":        uname.machine,
        "processor":   uname.processor or platform.processor(),
        "cpu_cores":   psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "boot_time":   datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
        "python":      platform.python_version(),
    })

@app.route("/api/stats")
def live_stats():
    cpu_percent  = psutil.cpu_percent(interval=0.2)
    cpu_per_core = psutil.cpu_percpu(interval=0.1)
    cpu_freq     = psutil.cpu_freq()
    mem          = psutil.virtual_memory()
    swap         = psutil.swap_memory()

    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device, "mountpoint": part.mountpoint,
                "fstype": part.fstype, "total": bytes_to_human(usage.total),
                "used": bytes_to_human(usage.used), "free": bytes_to_human(usage.free),
                "percent": usage.percent,
            })
        except PermissionError:
            pass

    net_io = psutil.net_io_counters()
    net_if = psutil.net_if_addrs()
    interfaces = []
    for iface, addrs in net_if.items():
        for addr in addrs:
            if addr.family == socket.AF_INET:
                interfaces.append({"name": iface, "ip": addr.address, "netmask": addr.netmask})

    procs = []
    for p in sorted(psutil.process_iter(["pid","name","cpu_percent","memory_percent","status"]),
                    key=lambda x: x.info["cpu_percent"] or 0, reverse=True)[:10]:
        procs.append({
            "pid": p.info["pid"], "name": p.info["name"],
            "cpu": round(p.info["cpu_percent"] or 0, 1),
            "mem": round(p.info["memory_percent"] or 0, 1),
            "status": p.info["status"],
        })

    return jsonify({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "uptime":    uptime_str(),
        "cpu": {
            "percent":  cpu_percent,
            "per_core": [round(c,1) for c in cpu_per_core],
            "freq_mhz": round(cpu_freq.current) if cpu_freq else 0,
        },
        "memory": {
            "percent": mem.percent, "total": bytes_to_human(mem.total),
            "used": bytes_to_human(mem.used), "available": bytes_to_human(mem.available),
        },
        "swap": {
            "percent": swap.percent, "total": bytes_to_human(swap.total),
            "used": bytes_to_human(swap.used), "free": bytes_to_human(swap.free),
        },
        "disks": disks,
        "network": {
            "bytes_sent": bytes_to_human(net_io.bytes_sent),
            "bytes_recv": bytes_to_human(net_io.bytes_recv),
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "interfaces": interfaces,
        },
        "processes": procs,
    })

if __name__ == "__main__":
    print("\n  SysWatch is running!")
    print("  Open: http://localhost:5000\n")
    app.run(debug=False, host="0.0.0.0", port=5000)
