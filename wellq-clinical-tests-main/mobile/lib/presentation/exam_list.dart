import 'package:flutter/material.dart';
import '../application/patient_controller.dart';
import '../domain/exam_query.dart';
import '../domain/models.dart';
import '../domain/patient_labels.dart';
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
        Text('Mis exámenes', style: Theme.of(context).textTheme.titleMedium),
        Text(
          c.online
              ? 'Tus documentos y su estado actual.'
              : 'Última lectura disponible. No confirma cambios del servidor.',
        ),
        const SizedBox(height: 8),
        const Text(
          'Búsqueda y orden: documentos cargados. Estado y tipo: servidor.',
        ),
        LabeledField(
          label: 'Buscar en títulos cargados',
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
                      tooltip: 'Limpiar búsqueda',
                      icon: const Icon(Icons.clear),
                      onPressed: () => setState(search.clear),
                    ),
            ),
          ),
        ),
        ExpansionTile(
          title: const Text('Filtrar y ordenar'),
          onExpansionChanged: (_) => searchFocus.unfocus(),
          children: [
            LabeledField(
              label: 'Estado en el servidor',
              child: select<String>(
                key: const ValueKey('exam-status'),
                value: c.filters.status ?? '',
                items: [
                  const DropdownMenuItem(value: '', child: Text('Todos')),
                  for (final value in ExamFilters.statuses)
                    DropdownMenuItem(
                      value: value,
                      child: Text(
                        examLabel(value),
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
              label: 'Tipo en el servidor',
              child: select<String>(
                key: const ValueKey('exam-type'),
                value: c.filters.type ?? '',
                items: [
                  const DropdownMenuItem(value: '', child: Text('Todos')),
                  for (final value in ExamFilters.types)
                    DropdownMenuItem(
                      value: value,
                      child: Text(
                        testTypeLabel(value)!,
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
                child: const Text('Quitar filtros del servidor'),
              ),
            LabeledField(
              label: 'Orden de documentos cargados',
              child: select<bool>(
                key: const ValueKey('exam-order'),
                value: oldest,
                items: const [
                  DropdownMenuItem(value: false, child: Text('Más recientes')),
                  DropdownMenuItem(value: true, child: Text('Más antiguos')),
                ],
                onChanged: (v) => setState(() => oldest = v ?? false),
              ),
            ),
          ],
        ),
        if (!c.filters.isEmpty)
          Text(
            'Filtro del servidor: ${c.filters.status == null ? 'todos los estados' : examLabel(c.filters.status!)} · ${c.filters.type == null ? 'todos los tipos' : testTypeLabel(c.filters.type)}',
          ),
        const SizedBox(height: 12),
        Semantics(
          liveRegion: true,
          child: Text(
            '${visible.length} de ${c.exams.length} documentos cargados en esta consulta.',
          ),
        ),
        if (c.busy) const LinearProgressIndicator(),
        if (visible.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 20),
            child: Text(
              c.exams.isNotEmpty
                  ? 'Sin coincidencias entre los documentos cargados. Puedes cargar más páginas o cambiar la búsqueda.'
                  : !c.online
                  ? 'No hay una lectura disponible. Verifica la conexión y consulta nuevamente.'
                  : !c.filters.isEmpty
                  ? 'No hay documentos para estos filtros. Puedes quitarlos o actualizar.'
                  : 'Sin exámenes en esta vista. Actualiza o carga el PDF sintético.',
            ),
          ),
        for (final e in visible) widget.card(e),
        if (c.cursor != null) ...[
          const Text(
            'Hay más páginas del servidor; aún no se buscaron sus títulos.',
          ),
          OutlinedButton(
            onPressed: c.busy || !c.online ? null : () => c.refresh(more: true),
            child: const Text('Cargar más'),
          ),
        ],
        TextButton(
          onPressed: c.busy ? null : () => c.refresh(),
          child: const Text('Actualizar listado'),
        ),
      ],
    );
  }
}
