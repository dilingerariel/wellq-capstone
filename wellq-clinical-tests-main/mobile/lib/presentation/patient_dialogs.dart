import '../l10n/localized_copy.dart';
import 'package:flutter/material.dart';

Future<bool> ask(BuildContext context, String title, String text) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: SingleChildScrollView(child: Text(text)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(context.l10n.back),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(context.l10n.confirmAction),
          ),
        ],
      ),
    ) ??
    false;
