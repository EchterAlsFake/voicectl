import QtQuick
import qs.Common
import qs.Modules.Plugins
import qs.Widgets

PluginSettings {
    id: root
    pluginId: VoicectlService.pluginId

    StyledText {
        width: parent.width
        text: "Voice Control Settings"
        font.pixelSize: Theme.fontSizeLarge
        font.weight: Font.Bold
        color: Theme.surfaceText
    }

    StyledText {
        width: parent.width
        text: "Configure the voice control status indicator and background polling on your bar."
        font.pixelSize: Theme.fontSizeSmall
        color: Theme.surfaceVariantText
        wrapMode: Text.WordWrap
    }

    ToggleSetting {
        settingKey: "showLabel"
        label: "Show Mode Label on Bar"
        description: "Display 'PRESENT', 'VOICE', or 'OFF' text next to the microphone icon on the bar."
        defaultValue: true
    }

    SliderSetting {
        settingKey: "pollInterval"
        label: "Status Refresh Interval"
        description: "How frequently to query voicectl daemon status in the background."
        defaultValue: 5000
        minimum: 2000
        maximum: 15000
        step: 1000
        unit: "ms"
        leftIcon: "schedule"
    }
}
