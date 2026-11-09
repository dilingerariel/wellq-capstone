import 'models.dart';

// Only query parameters supported by the patient OpenAPI list endpoint.
class ExamFilters {
  const ExamFilters({this.status, this.type});
  final String? status, type;
  static const statuses = [
    'initiated',
    'object_uploaded',
    'processing',
    'ready_for_review',
    'rejected',
    'failed',
  ];
  static const types = [
    'blood_test',
    'urine_test',
    'imaging',
    'pathology',
    'other',
  ];
  bool get isEmpty => status == null && type == null;
  String path({String? cursor}) {
    if ((status != null && !statuses.contains(status)) ||
        (type != null && !types.contains(type))) {
      throw const ApiFailure(422, 'INVALID_LIST_FILTER');
    }
    final query = <String, String>{};
    if (status != null) {
      query['status'] = status!;
    }
    if (type != null) {
      query['test_type'] = type!;
    }
    if (cursor != null) {
      query['cursor'] = cursor;
    }
    return Uri(
      path: '/api/v1/clinical-tests',
      queryParameters: query.isEmpty ? null : query,
    ).toString();
  }
}

// Search and alternate ordering cover loaded results only, never unseen pages.
List<Exam> searchLoadedExams(
  List<Exam> loaded,
  String text, {
  bool oldestFirst = false,
}) {
  final words = text
      .trim()
      .toLowerCase()
      .split(RegExp(r'\s+'))
      .where((w) => w.isNotEmpty);
  final result = loaded
      .where((e) => words.every((w) => e.title.toLowerCase().contains(w)))
      .toList();
  final order = {for (var i = 0; i < loaded.length; i++) loaded[i].id: i};
  result.sort((a, b) {
    final date = oldestFirst
        ? a.date.compareTo(b.date)
        : b.date.compareTo(a.date);
    return date == 0 ? order[a.id]!.compareTo(order[b.id]!) : date;
  });
  return result;
}
