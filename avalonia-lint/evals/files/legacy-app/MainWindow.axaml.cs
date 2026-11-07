using Avalonia.Controls;
using Avalonia.Input;

namespace LegacyApp;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        this.AttachDevTools();
    }

    private async void OnOpen(object? sender, Avalonia.Interactivity.RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog();
        var settings = new SettingsWindow();
        await settings.ShowDialog();
        var text = await Clipboard!.GetTextAsync();
        var result = LoadAsync().GetAwaiter().GetResult();
    }
}
