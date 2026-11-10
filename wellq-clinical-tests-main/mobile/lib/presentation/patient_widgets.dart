import '../l10n/localized_copy.dart';
import 'package:flutter/material.dart';

class LabeledField extends StatelessWidget {
  const LabeledField({super.key, required this.label, required this.child});
  final String label;
  final Widget child;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 8),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(
            context,
          ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 4),
        Semantics(label: label, child: child),
      ],
    ),
  );
}

class PatientNavigation extends StatelessWidget {
  const PatientNavigation({
    super.key,
    required this.selected,
    required this.onSelected,
  });
  final int selected;
  final ValueChanged<int> onSelected;
  List<String> localizedLabels(BuildContext context) => [
    context.l10n.home,
    context.l10n.exams,
    context.l10n.upload,
    context.l10n.pending,
    context.l10n.settings,
  ];
  List<String> localizedCaptions(BuildContext context) => [
    context.l10n.home,
    context.l10n.docsCaption,
    context.l10n.upload,
    context.l10n.queueCaption,
    context.l10n.settings,
  ];
  static const icons = [
    Icons.space_dashboard_outlined,
    Icons.folder_open_outlined,
    Icons.upload_file_outlined,
    Icons.sync_outlined,
    Icons.settings_outlined,
  ];
  @override
  Widget build(BuildContext context) {
    final labels = localizedLabels(context);
    final captions = localizedCaptions(context);
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainer,
      child: SafeArea(
        top: false,
        child: LayoutBuilder(
          builder: (context, box) {
            final style = Theme.of(context).textTheme.labelMedium!;
            final scaler = MediaQuery.textScalerOf(context);
            final room = box.maxWidth / captions.length - 8;
            final showCaptions = captions.every((label) {
              final painter = TextPainter(
                text: TextSpan(text: label, style: style),
                textDirection: Directionality.of(context),
                textScaler: scaler,
              )..layout();
              final fits = painter.width <= room;
              painter.dispose();
              return fits;
            });
            return Row(
              children: [
                for (var i = 0; i < labels.length; i++)
                  Expanded(
                    child: Semantics(
                      selected: selected == i,
                      button: true,
                      label: labels[i],
                      onTap: () => onSelected(i),
                      excludeSemantics: true,
                      child: Tooltip(
                        message: labels[i],
                        child: InkWell(
                          key: ValueKey('patient-tab/$i'),
                          onTap: () => onSelected(i),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                              vertical: 8,
                              horizontal: 4,
                            ),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Container(
                                  width: 48,
                                  height: 32,
                                  decoration: BoxDecoration(
                                    color: selected == i
                                        ? Theme.of(
                                            context,
                                          ).colorScheme.secondaryContainer
                                        : Colors.transparent,
                                    borderRadius: BorderRadius.circular(16),
                                  ),
                                  child: Icon(
                                    icons[i],
                                    color: selected == i
                                        ? Theme.of(
                                            context,
                                          ).colorScheme.onSecondaryContainer
                                        : Theme.of(
                                            context,
                                          ).colorScheme.onSurface,
                                  ),
                                ),
                                if (showCaptions) ...[
                                  const SizedBox(height: 2),
                                  Text(
                                    captions[i],
                                    style: style,
                                    maxLines: 1,
                                    softWrap: false,
                                  ),
                                ],
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}
