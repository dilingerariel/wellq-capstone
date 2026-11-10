import 'dart:io';
import 'dart:convert';
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:wellq_mobile/application/patient_controller.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/presentation/exam_screen.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'foundation_test.dart' show patient, FixedIdentity, response;
import 'phase2_domain_test.dart' show proposal;

void main() {
  WidgetController.hitTestWarningShouldBeFatal = true;
  for (final state in ['confirmed', 'discarded', 'rejected']) {
    testWidgets(
      '$state shows translated read-only values without another confirmation',
      (t) async {
        final db = LocalStore(NativeDatabase.memory());
        final c = PatientController(
          ApiClient(
            client: MockClient(
              (r) async => response(
                r.url.path.endsWith('/extraction')
                    ? (proposal()..['status'] = state)
                    : {'title': 'SYNTHETIC', 'status': 'ready_for_review'},
              ),
            ),
          ),
          FixedIdentity(patient()),
          db,
          Directory.systemTemp,
        )..session = patient();
        await t.pumpWidget(
          MaterialApp(
            home: ExamScreen(
              c: c,
              exam: const Exam('id', 'SYNTHETIC', '', 'ready_for_review'),
            ),
          ),
        );
        await t.pumpAndSettle();
        expect(find.textContaining('Coteja la propuesta'), findsNothing);
        expect(find.text('Revisar y confirmar'), findsNothing);
        expect(find.text('90 mg/dL'), findsOneWidget);
        expect(find.text('Pendiente de revisión profesional'), findsOneWidget);
        expect(find.text('ready_for_review'), findsNothing);
        expect(find.text('Ver documento'), findsNothing);
        await t.pumpWidget(const SizedBox.shrink());
        c.dispose();
        await db.close();
      },
    );
  }
  testWidgets(
    '409 fetches latest state and blocks resubmission until explicit review',
    (t) async {
      final db = LocalStore(NativeDatabase.memory());
      var reads = 0, writes = 0;
      final c = PatientController(
        ApiClient(
          client: MockClient((r) async {
            if (r.method == 'PATCH') {
              writes++;
              return response({}, 409);
            }
            if (r.url.path.endsWith('/extraction')) {
              reads++;
              return response(proposal());
            }
            return response({
              'title': 'SYNTHETIC',
              'status': 'ready_for_review',
            });
          }),
        ),
        FixedIdentity(patient()),
        db,
        Directory.systemTemp,
      )..session = patient();
      await t.pumpWidget(
        MaterialApp(
          home: ExamScreen(
            c: c,
            exam: const Exam('id', 'SYNTHETIC', '', 'processing'),
          ),
        ),
      );
      await t.pumpAndSettle();
      for (final label in [
        'He comprobado que este documento me corresponde.',
        'He cotejado valores, unidades y campos de baja confianza.',
      ]) {
        await t.scrollUntilVisible(
          find.text(label),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await t.pumpAndSettle();
        await t.ensureVisible(find.widgetWithText(CheckboxListTile, label));
        await t.pumpAndSettle();
        await t.tap(find.text(label));
        await t.pumpAndSettle();
      }
      await t.ensureVisible(find.text('Revisar y confirmar'));
      await t.tap(find.text('Revisar y confirmar'));
      await t.pumpAndSettle();
      expect(writes, 0);
      await t.tap(find.text('Confirmar acción'));
      await t.pumpAndSettle();
      expect(writes, 1);
      expect(reads, 2);
      expect(
        t
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Reintentar el mismo envío'),
            )
            .onPressed,
        isNull,
      );
      await t.scrollUntilVisible(
        find.text('Consultar propuesta actual'),
        100,
        scrollable: find.byType(Scrollable).first,
      );
      await t.pumpAndSettle();
      await t.ensureVisible(
        find.widgetWithText(OutlinedButton, 'Consultar propuesta actual'),
      );
      await t.pumpAndSettle();
      await t.tap(find.text('Consultar propuesta actual'));
      await t.pumpAndSettle();
      await t.tap(find.text('Confirmar acción'));
      await t.pumpAndSettle();
      expect(reads, 3);
      expect(writes, 1);
      await t.pumpWidget(const SizedBox.shrink());
      c.dispose();
      await db.close();
    },
  );
  testWidgets(
    'edits are previewed as original to new and only contracted keys are sent',
    (t) async {
      final db = LocalStore(NativeDatabase.memory());
      Json? sent;
      final c = PatientController(
        ApiClient(
          client: MockClient((r) async {
            if (r.method == 'PATCH') {
              // Parsing stays in the test; never log clinical request bodies.
              sent = apiBody(r.body);
              return response(proposal()..['status'] = 'confirmed');
            }
            if (r.url.path.endsWith('/extraction')) return response(proposal());
            if (r.url.path == '/api/v1/clinical-tests') {
              return response({'items': [], 'next_cursor': null});
            }
            return response({
              'title': 'SYNTHETIC',
              'status': 'ready_for_review',
            });
          }),
        ),
        FixedIdentity(patient()),
        db,
        Directory.systemTemp,
      )..session = patient();
      await t.pumpWidget(
        MaterialApp(
          home: ExamScreen(
            c: c,
            exam: const Exam('id', 'SYNTHETIC', '', 'processing'),
          ),
        ),
      );
      await t.pumpAndSettle();
      await t.ensureVisible(find.byKey(const ValueKey('review/glucose/value')));
      await t.enterText(
        find.byKey(const ValueKey('review/glucose/value')),
        '91',
      );
      for (final label in [
        'He comprobado que este documento me corresponde.',
        'He cotejado valores, unidades y campos de baja confianza.',
      ]) {
        await t.scrollUntilVisible(
          find.text(label),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await t.pumpAndSettle();
        await t.ensureVisible(find.widgetWithText(CheckboxListTile, label));
        await t.pumpAndSettle();
        await t.tap(find.text(label));
        await t.pumpAndSettle();
      }
      await t.ensureVisible(find.text('Revisar y confirmar'));
      await t.tap(find.text('Revisar y confirmar'));
      await t.pumpAndSettle();
      expect(find.textContaining('90 mg/dL → 91 mg/dL'), findsOneWidget);
      expect(sent, isNull);
      await t.tap(find.text('Confirmar acción'));
      await t.pumpAndSettle();
      expect(sent!['extraction_id'], 'proposal-version-1');
      expect((sent!['marker_edits'] as List).single, {
        'op': 'update',
        'marker_code': 'glucose',
        'value_raw': '91',
        'unit_raw': 'mg/dL',
      });
      expect(find.text('Revisar y confirmar'), findsNothing);
      await t.pumpWidget(const SizedBox.shrink());
      c.dispose();
      await db.close();
    },
  );
}

Json apiBody(String body) => Map<String, dynamic>.from(jsonDecode(body) as Map);
