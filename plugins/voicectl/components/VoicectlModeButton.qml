import QtQuick
import qs.Common
import qs.Widgets

Rectangle {
    id: root
    height: 38
    radius: Theme.cornerRadius
    property string targetMode: "presentation"
    property string label: "Presentation"
    property string iconName: "slideshow"
    property bool isSelected: false
    property bool isAvailable: true

    signal clicked

    color: isSelected 
        ? Theme.primaryContainer 
        : (mouseArea.containsMouse ? Theme.surfaceContainerHighest : Theme.surfaceContainerLow)
    border.width: isSelected ? 1 : 0
    border.color: Theme.primary

    Row {
        anchors.centerIn: parent
        spacing: Theme.spacingS

        DankIcon {
            anchors.verticalCenter: parent.verticalCenter
            name: root.iconName
            size: 18
            color: root.isSelected ? Theme.primary : Theme.surfaceText
        }

        StyledText {
            anchors.verticalCenter: parent.verticalCenter
            text: root.label
            font.pixelSize: Theme.fontSizeSmall
            font.weight: root.isSelected ? Font.Bold : Font.Normal
            color: root.isSelected ? Theme.primary : Theme.surfaceText
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
