pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import qs.Common
import qs.Services

Singleton {
    id: root

    readonly property string pluginId: "voicectl"
    readonly property string cliBinary: "/usr/local/bin/voicectl"

    property bool isAvailable: false
    property bool isBusy: false
    property string mode: "off"
    property string statusText: "Voice Control"
    property string inferenceDevice: "NPU"
    property string asrBackend: "OpenVINO"
    property string microphone: "default"
    property string lastCommand: "none"
    property string lastTranscript: ""
    property real lastLatencyMs: 0.0
    property int totalCommands: 0
    property bool showLabel: true
    property int pollInterval: 5000

    signal statusChanged
    signal availabilityChanged

    Component.onCompleted: {
        loadSettings();
        checkStatus();
    }

    Connections {
        target: PluginService
        function onPluginDataChanged(changedPluginId) {
            if (changedPluginId === root.pluginId) {
                loadSettings();
            }
        }
    }

    function loadSettings() {
        showLabel = PluginService.loadPluginData(pluginId, "showLabel") ?? true;
        pollInterval = PluginService.loadPluginData(pluginId, "pollInterval") ?? 5000;
        pollTimer.interval = Math.max(2000, pollInterval);
    }

    function saveSettings() {
        PluginService.savePluginData(pluginId, "showLabel", showLabel);
        PluginService.savePluginData(pluginId, "pollInterval", pollInterval);
    }

    function parseStatus(jsonText) {
        try {
            const data = JSON.parse(jsonText.trim());
            const wasAvail = isAvailable;
            const wasMode = mode;

            isAvailable = (data.available !== false && data.service === "running");
            mode = (data.mode || "off").toLowerCase();

            if (!isAvailable) {
                statusText = "Service Inactive";
            } else if (mode === "presentation") {
                statusText = "Presentation Mode";
            } else if (mode === "normal") {
                statusText = "Normal Mode";
            } else {
                statusText = "Muted (Off)";
            }

            if (data.inference_device)
                inferenceDevice = data.inference_device;
            if (data.asr_backend)
                asrBackend = data.asr_backend;
            if (data.microphone)
                microphone = data.microphone;
            if (data.last_command)
                lastCommand = data.last_command;
            if (data.last_transcript)
                lastTranscript = data.last_transcript;
            if (data.last_latency_ms !== undefined)
                lastLatencyMs = data.last_latency_ms;
            if (data.total_commands !== undefined)
                totalCommands = data.total_commands;

            if (wasAvail !== isAvailable)
                availabilityChanged();
            if (wasMode !== mode)
                statusChanged();
        } catch (e) {
            console.warn(`[${pluginId}] Failed to parse status JSON:`, e);
        }
    }

    function checkStatus() {
        Proc.runCommand(`${pluginId}.status`, [cliBinary, "status", "--json"], (stdout, exitCode) => {
            if (stdout && exitCode === 0) {
                parseStatus(stdout);
            } else {
                isAvailable = false;
                statusText = "Service Unavailable";
                availabilityChanged();
            }
        }, 100);
    }

    function toggle() {
        if (isBusy)
            return;
        isBusy = true;
        Proc.runCommand(`${pluginId}.toggle`, [cliBinary, "toggle", "--json"], (stdout, exitCode) => {
            isBusy = false;
            if (exitCode === 0 && stdout) {
                checkStatus();
            } else {
                ToastService.showError("Voice Control Error", stdout || "Failed to toggle mode");
            }
        }, 150);
    }

    function setMode(newMode) {
        if (isBusy)
            return;
        isBusy = true;
        Proc.runCommand(`${pluginId}.setMode`, [cliBinary, "mode", newMode, "--json"], (stdout, exitCode) => {
            isBusy = false;
            if (exitCode === 0 && stdout) {
                checkStatus();
            } else {
                ToastService.showError("Voice Control Error", stdout || "Failed to set mode");
            }
        }, 150);
    }

    function refresh() {
        checkStatus();
    }

    Timer {
        id: pollTimer
        interval: root.pollInterval
        running: true
        repeat: true
        onTriggered: {
            root.checkStatus();
        }
    }
}
