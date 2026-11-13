import '../l10n/localized_copy.dart';
import 'package:flutter/material.dart';

class DemoAccessDialog extends StatefulWidget {
  const DemoAccessDialog({super.key});
  @override
  State<DemoAccessDialog> createState() => _DemoAccessDialogState();
}

class _DemoAccessDialogState extends State<DemoAccessDialog> {
  final code = TextEditingController();
  @override
  void dispose() {
    code.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(context.l10n.demoAccessCode),
    content: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(context.l10n.demoAccessHelp),
          const SizedBox(height: 12),
          TextField(
            controller: code,
            obscureText: true,
            autocorrect: false,
            enableSuggestions: false,
            decoration: InputDecoration(labelText: context.l10n.demoAccessCode),
          ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: Text(context.l10n.back),
      ),
      FilledButton(
        onPressed: () {
          if (code.text.trim().isNotEmpty) {
            Navigator.pop(context, code.text.trim());
          }
        },
        child: Text(context.l10n.confirmAction),
      ),
    ],
  );
}

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
