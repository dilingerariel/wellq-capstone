import 'package:flutter/material.dart';
import '../application/language_controller.dart';
import '../l10n/localized_copy.dart';
import 'patient_widgets.dart';

class LanguageSelector extends StatelessWidget {
  const LanguageSelector({super.key, required this.language});
  final LanguageController language;
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: language,
    builder: (context, _) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LabeledField(
          label: context.l10n.language,
          child: DropdownButton<String>(
            key: const ValueKey('language-selector'),
            value: language.code,
            isExpanded: true,
            items: [
              DropdownMenuItem(value: 'es', child: Text(context.l10n.spanish)),
              DropdownMenuItem(value: 'en', child: Text(context.l10n.english)),
            ],
            onChanged: (code) {
              if (code != null) language.select(code);
            },
          ),
        ),
        Text(context.l10n.languageHint),
        if (language.saveFailed)
          Semantics(
            liveRegion: true,
            child: Text(context.l10n.languageSaveFailed),
          ),
      ],
    ),
  );
}
