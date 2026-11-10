import '../l10n/localized_copy.dart';
import 'package:flutter/material.dart';
import '../application/patient_controller.dart';
import '../domain/exam_query.dart';
import '../domain/models.dart';
import 'patient_widgets.dart';

class ExamList extends StatefulWidget {
  const ExamList({super.key, required this.c, required this.card});
  final PatientController c;
  final Widget Function(Exam) card;
  @override
  State<ExamList> createState() => _ExamListState();
}

class _ExamListState extends State<ExamList> {
  final search = TextEditingController();
  final searchFocus = FocusNode();
  bool oldest = false;
  @override
  void dispose() {
    search.dispose();
    searchFocus.dispose();
    super.dispose();
  }

  Widget select<T>({
    required Key key,
    required T value,
    required List<DropdownMenuItem<T>> items,
    required ValueChanged<T?>? onChanged,
  }) => InputDecorator(
    decoration: const InputDecoration(
      border: OutlineInputBorder(),
      contentPadding: EdgeInsets.symmetric(horizontal: 12),
    ),
    child: DropdownButtonHideUnderline(
      child: DropdownButton<T>(
        key: key,
        value: value,
        isExpanded: true,
        items: items,
        onTap: searchFocus.unfocus,
        onChanged: onChanged,
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final c = widget.c;
    final visible = searchLoadedExams(
      c.exams,
      search.text,
      oldestFirst: oldest,
    );
    final canFilter = c.online && !c.busy;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          context.l10n.myExams,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        Text(
          c.online
              ? context.l10n.documentsStatusSubtitle
              : context.l10n.lastAvailableReading,
        ),
        const SizedBox(height: 8),
        Text(context.l10n.searchScope),
        LabeledField(
          label: context.l10n.searchLoadedTitles,
          child: TextField(
            key: const ValueKey('exam-search'),
            controller: search,
            focusNode: searchFocus,
            maxLength: 200,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => searchFocus.unfocus(),
            onTapOutside: (_) => searchFocus.unfocus(),
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(
              prefixIcon: const Icon(Icons.search),
              suffixIcon: search.text.isEmpty
                  ? null
                  : IconButton(
                      tooltip: context.l10n.clearSearch,
                      icon: const Icon(Icons.clear),
                      onPressed: () => setState(search.clear),
                    ),
            ),
          ),
        ),
        ExpansionTile(
          title: Text(context.l10n.filterSort),
          onExpansionChanged: (_) => searchFocus.unfocus(),
          children: [
            LabeledField(
              label: context.l10n.serverStatus,
              child: select<String>(
                key: const ValueKey('exam-status'),
                value: c.filters.status ?? '',
                items: [
                  DropdownMenuItem(value: '', child: Text(context.l10n.all)),
                  for (final value in ExamFilters.statuses)
                    DropdownMenuItem(
                      value: value,
                      child: Text(
                        localizedExamLabel(context, value),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
                onChanged: !canFilter
                    ? null
                    : (v) => c.refresh(
                        filtering: ExamFilters(
                          status: v == '' ? null : v,
                          type: c.filters.type,
                        ),
                      ),
              ),
            ),
            LabeledField(
              label: context.l10n.serverType,
              child: select<String>(
                key: const ValueKey('exam-type'),
                value: c.filters.type ?? '',
                items: [
                  DropdownMenuItem(value: '', child: Text(context.l10n.all)),
                  for (final value in ExamFilters.types)
                    DropdownMenuItem(
                      value: value,
                      child: Text(
                        localizedTestTypeLabel(context, value)!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
                onChanged: !canFilter
                    ? null
                    : (v) => c.refresh(
                        filtering: ExamFilters(
                          status: c.filters.status,
                          type: v == '' ? null : v,
                        ),
                      ),
              ),
            ),
            if (!c.filters.isEmpty)
              TextButton(
                onPressed: !canFilter
                    ? null
                    : () => c.refresh(filtering: const ExamFilters()),
                child: Text(context.l10n.removeServerFilters),
              ),
            LabeledField(
              label: context.l10n.loadedDocumentOrder,
              child: select<bool>(
                key: const ValueKey('exam-order'),
                value: oldest,
                items: [
                  DropdownMenuItem(
                    value: false,
                    child: Text(context.l10n.newestFirst),
                  ),
                  DropdownMenuItem(
                    value: true,
                    child: Text(context.l10n.oldestFirst),
                  ),
                ],
                onChanged: (v) => setState(() => oldest = v ?? false),
              ),
            ),
          ],
        ),
        if (!c.filters.isEmpty)
          Text(
            context.l10n.serverFilter(
              c.filters.status == null
                  ? context.l10n.allStatuses
                  : localizedExamLabel(context, c.filters.status!),
              c.filters.type == null
                  ? context.l10n.allTypes
                  : localizedTestTypeLabel(context, c.filters.type)!,
            ),
          ),
        const SizedBox(height: 12),
        Semantics(
          liveRegion: true,
          child: Text(context.l10n.resultCount(visible.length, c.exams.length)),
        ),
        if (c.busy) const LinearProgressIndicator(),
        if (visible.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 20),
            child: Text(
              c.exams.isNotEmpty
                  ? context.l10n.noMatches
                  : !c.online
                  ? context.l10n.noReading
                  : !c.filters.isEmpty
                  ? context.l10n.noFilteredDocuments
                  : context.l10n.noExamsView,
            ),
          ),
        for (final e in visible) widget.card(e),
        if (c.cursor != null) ...[
          Text(context.l10n.morePagesHint),
          OutlinedButton(
            onPressed: c.busy || !c.online ? null : () => c.refresh(more: true),
            child: Text(context.l10n.loadMore),
          ),
        ],
        TextButton(
          onPressed: c.busy ? null : () => c.refresh(),
          child: Text(context.l10n.refreshList),
        ),
      ],
    );
  }
}
