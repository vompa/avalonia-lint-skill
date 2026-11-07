# Documentation conflicts

Where the Avalonia 12.1 documentation contradicts itself or the shipped API, the catalog follows the API of the Avalonia 12.1.4 NuGet packages (checked in their XML documentation and, where needed, by reflection). This file records each decision so a reviewer can tell "differs on purpose" from "differs by mistake".

## Docs vs. shipped API (Avalonia 12.1.4)

| Topic | Documentation says | 12.1.4 has | Catalog |
|---|---|---|---|
| `TextBox.Watermark`, `UseFloatingWatermark` | renamed / no longer exists | still present, `[Obsolete]` | AV-MIG-24 is a `warning`, not an `error` |
| `Window.SystemDecorations` | replaced by `WindowDecorations` | still present, `[Obsolete]` | AV-MIG-13 `warning`; `ExtendClientAreaChromeHints` is really gone (AV-APP-25 `error`) |
| `Application.Current.Dispatcher` | some pages say it does not exist | `AvaloniaObject.Dispatcher` exists | no rule; use of `Dispatcher.UIThread` is still advised |
| `Popup.Placement` | one page implies `BottomEdgeAlignedRight` is missing | `PlacementMode.BottomEdgeAlignedRight` exists | rule dropped |
| `FlyoutPlacementMode` | named on menu pages | does not exist; flyouts use `PlacementMode` | rule dropped |
| `GetVisualRoot`, `Visual.VisualRoot` | removed in 12 | still present | not flagged |
| `BindingPlugins`, `IPopupHost`, `LayoutManager`, `KeyboardNavigationHandler` | removed | exist but are internal | still `error` (CS0122 when used) |
| `ControlTheme` inside `Styles` | not allowed | compiles (`ControlTheme` implements `IStyle`) | AV-MIG-40 `warning` |
| `TemplateBinding` | OneWay only | `TemplateBinding.Mode` exists | rule dropped |
| `FuncMultiValueConverter` constructor | changed | both constructors present, not obsolete | rule dropped |
| `UseSkia()` without `UseHarfBuzz()` | throws | headless test setups with `UseSkia()` alone run | AV-MIG-05 `warning`, skipped for `UseHeadless` |
| `TextAlignment` values | five values listed | also `Start` and `End` | enum check uses all seven |
| `AutoCompleteBox.FilterMode` | twelve values listed | fourteen, incl. `None` and `Custom` | enum check uses all fourteen |
| `NumericUpDown` placeholder | not documented | `NumericUpDown.PlaceholderText` exists | allowed |

## Docs vs. docs

- Style precedence: `property-setters.md` describes order and proximity, another page implies CSS-like specificity. The catalog follows `property-setters.md` (AV-STYLE-13).
- Key gestures: both `Ctrl+1` and `Ctrl+D1` appear in examples; the related rule is `info` only.
- Theme include paths: DataGrid uses `.../Themes/Fluent.xaml`, TreeDataGrid and PdfViewer `.../Themes/Fluent.axaml`. Each rule uses the form its page documents.
- DataGrid page: example still pins `Avalonia.Controls.DataGrid` 11.0.0 while the text requires a matching version.
- Canvas page: text uses `Canvas.Left`/`Canvas.Top`, the example omits the prefix. The catalog follows the text.
- DockPanel page: "the last child must not be docked" conflicts with `LastChildFill="False"`. Only the attached-property prefix is checked automatically.
- ColorView page: recommends both `Color` and `HsvColor` for binding. Not checked.
- CalendarDatePicker page: table says `SelectedDate` is `DateTime?`, example binds `DateTimeOffset?`. Not checked.
- Compiled bindings: `docs/xaml/compilation` still describes Avalonia 11 reflection defaults; the catalog follows `docs/data-binding/compiled-bindings` (compiled by default, type inference for `#Name.DataContext` since 11.3).
- Multi-binding page: an example binds `ConverterParameter` with `{Binding}`, which another page says is not possible. AV-BIND-05 is a `warning`.
- Menu flyouts: one page shows `Separator` in a `MenuFlyout`, another says it is not supported. No rule.
- Pro licensing: PdfViewer requires `AvaloniaUI.Licensing` in every head, TreeDataGrid only mentions `AvaloniaUILicenseKey`. The catalog checks only that a key is not committed in clear text and that Pro packages have a key.
