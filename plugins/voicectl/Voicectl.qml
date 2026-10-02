import QtQuick
import Quickshell
import qs.Common
import qs.Services
import qs.Widgets
import qs.Modules.Plugins
import "./components"

PluginComponent {
    id: root

    readonly property bool isAvailable: VoicectlService.isAvailable
    readonly property bool isBusy: VoicectlService.isBusy
    readonly property string mode: VoicectlService.mode
    readonly property string statusText: VoicectlService.statusText
    readonly property string inferenceDevice: VoicectlService.inferenceDevice
    readonly property string lastCommand: VoicectlService.lastCommand
    readonly property real lastLatencyMs: VoicectlService.lastLatencyMs
    readonly property int totalCommands: VoicectlService.totalCommands
    readonly property bool showLabel: VoicectlService.showLabel

    Component.onCompleted: {
        console.log("[voicectl] Quickshell plugin loaded successfully");
    }

    ccWidgetIcon: {
        if (!isAvailable)
            return "mic_off";
        if (mode === "presentation")
            return "slideshow";
        if (mode === "normal")
            return "mic";
        return "mic_off";
    }

    ccWidgetPrimaryText: "Voice Control"
    ccWidgetSecondaryText: statusText
    ccWidgetIsActive: isAvailable && mode !== "off"
    pillClickAction: () => VoicectlService.toggle()
    pillRightClickAction: () => root.triggerPopout()
    ccDetailHeight: 230

    onCcWidgetToggled: {
        VoicectlService.toggle();
    }

    onCcWidgetExpanded: {
        VoicectlService.refresh();
    }

    // ─── Horizontal Bar Pill ───
    horizontalBarPill: Component {
        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacingXS

            DankIcon {
                anchors.verticalCenter: parent.verticalCenter
                name: {
                    if (!root.isAvailable)
                        return "error";
                    if (root.mode === "presentation")
                        return "slideshow";
                    if (root.mode === "normal")
                        return "mic";
                    return "mic_off";
                }
                size: Theme.barIconSize(root.barThickness, -2, root.barConfig?.maximizeWidgetIcons, root.barConfig?.iconScale)
                color: {
                    if (!root.isAvailable)
                        return Theme.error;
                    if (root.mode === "presentation")
                        return Theme.primary;
                    if (root.mode === "normal")
                        return Theme.tertiary ?? Theme.primary;
                    return Theme.surfaceVariantText;
                }
            }

            StyledText {
                visible: root.showLabel
                anchors.verticalCenter: parent.verticalCenter
                text: {
                    if (!root.isAvailable)
                        return "OFFLINE";
                    if (root.mode === "presentation")
                        return "PRESENT";
                    if (root.mode === "normal")
                        return "VOICE";
                    return "OFF";
                }
                font.pixelSize: Theme.fontSizeSmall
                font.weight: Font.Bold
                color: {
                    if (!root.isAvailable)
                        return Theme.error;
                    if (root.mode !== "off")
                        return Theme.surfaceText;
                    return Theme.surfaceVariantText;
                }
            }
        }
    }

    // ─── Control Center Card / Popout ───
    ccDetailContent: Component {
        StyledRect {
            color: Theme.surfaceContainerHigh
            radius: Theme.cornerRadius
            border.width: 0
            height: cardCol.height + Theme.spacingL * 2
            anchors.fill: parent

            Column {
                id: cardCol
                anchors.fill: parent
                anchors.margins: Theme.spacingL
                spacing: Theme.spacingM

                // Header Row
                Item {
                    width: parent.width
                    height: 40

                    Row {
                        spacing: Theme.spacingM
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter

                        DankIcon {
                            name: root.mode === "presentation" ? "slideshow" : (root.mode === "normal" ? "mic" : "mic_off")
                            size: 24
                            color: root.mode !== "off" ? Theme.primary : Theme.surfaceVariantText
                        }

                        Column {
                            StyledText {
                                text: root.statusText
                                font.pixelSize: Theme.fontSizeMedium
                                font.weight: Font.Bold
                                color: Theme.surfaceText
                            }
                            StyledText {
                                text: `Inference: ${root.inferenceDevice} (OpenVINO)`
                                font.pixelSize: Theme.fontSizeExtraSmall
                                color: Theme.surfaceVariantText
                            }
                        }
                    }

                    DankActionButton {
                        iconName: "refresh"
                        iconColor: Theme.surfaceVariantText
                        buttonSize: 28
                        tooltipText: "Refresh voicectl"
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        onClicked: VoicectlService.refresh()
                    }
                }

                // Mode Selection Buttons
                Row {
                    width: parent.width
                    spacing: Theme.spacingS

                    VoicectlModeButton {
                        width: (parent.width - Theme.spacingS * 2) / 3
                        targetMode: "presentation"
                        label: "Present"
                        iconName: "slideshow"
                        isSelected: root.mode === "presentation"
                        onClicked: VoicectlService.setMode("presentation")
                    }

                    VoicectlModeButton {
                        width: (parent.width - Theme.spacingS * 2) / 3
                        targetMode: "normal"
                        label: "Normal"
                        iconName: "mic"
                        isSelected: root.mode === "normal"
                        onClicked: VoicectlService.setMode("normal")
                    }

                    VoicectlModeButton {
                        width: (parent.width - Theme.spacingS * 2) / 3
                        targetMode: "off"
                        label: "Off"
                        iconName: "mic_off"
                        isSelected: root.mode === "off"
                        onClicked: VoicectlService.setMode("off")
                    }
                }

                // Diagnostic Info Row
                StyledRect {
                    width: parent.width
                    height: 52
                    radius: Theme.cornerRadiusSmall
                    color: Theme.surfaceContainerLow
                    border.width: 0

                    Row {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingS
                        spacing: Theme.spacingL

                        Column {
                            StyledText {
                                text: "Last Command"
                                font.pixelSize: Theme.fontSizeExtraSmall
                                color: Theme.surfaceVariantText
                            }
                            StyledText {
                                text: root.lastCommand !== "none" ? root.lastCommand : "—"
                                font.pixelSize: Theme.fontSizeSmall
                                font.weight: Font.Medium
                                color: Theme.surfaceText
                            }
                        }

                        Column {
                            StyledText {
                                text: "Latency"
                                font.pixelSize: Theme.fontSizeExtraSmall
                                color: Theme.surfaceVariantText
                            }
                            StyledText {
                                text: root.lastLatencyMs > 0 ? `${root.lastLatencyMs.toFixed(0)} ms` : "—"
                                font.pixelSize: Theme.fontSizeSmall
                                font.weight: Font.Medium
                                color: Theme.primary
                            }
                        }

                        Column {
                            StyledText {
                                text: "Total Actions"
                                font.pixelSize: Theme.fontSizeExtraSmall
                                color: Theme.surfaceVariantText
                            }
                            StyledText {
                                text: `${root.totalCommands}`
                                font.pixelSize: Theme.fontSizeSmall
                                font.weight: Font.Medium
                                color: Theme.surfaceText
                            }
                        }
                    }
                }
            }
        }
    }

    // ─── Popout Content ───
    popoutContent: Component {
        Loader {
            sourceComponent: root.ccDetailContent
            width: root.popoutWidth
        }
    }

    popoutWidth: 360
    popoutHeight: 230
}
