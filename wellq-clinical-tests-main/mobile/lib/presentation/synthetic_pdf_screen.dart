import 'dart:typed_data';
import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:pdfrx/pdfrx.dart';
import '../domain/sample_policy.dart';

Uint8List verifiedSyntheticBytes(List<int> bytes) {
  if (bytes.length > 20 * 1024 * 1024 ||
      sha256.convert(bytes).toString() != syntheticPdfSha256) {
    throw const FormatException('Synthetic PDF integrity check failed');
  }
  return Uint8List.fromList(bytes);
}

// Memory-only source. No download, cache, external links or export action.
class SyntheticPdfScreen extends StatefulWidget {
  const SyntheticPdfScreen({super.key, required this.load});
  final Future<Uint8List> Function() load;
  @override
  State<SyntheticPdfScreen> createState() => _SyntheticPdfScreenState();
}

class _SyntheticPdfScreenState extends State<SyntheticPdfScreen> {
  late final Future<Uint8List> data = Future<Uint8List>.sync(
    widget.load,
  ).then(verifiedSyntheticBytes);
  final controller = PdfViewerController();
  final budget = PdfImageCacheBudget(maximumBytes: 32 * 1024 * 1024);
  bool ready = false;
  int pages = 0;
  @override
  void dispose() {
    budget.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Documento sintético')),
    body: SafeArea(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 8,
              children: [
                const Text('Sin uso clínico'),
                if (ready) Text('$pages página(s)'),
                IconButton(
                  tooltip: 'Alejar documento',
                  onPressed: ready
                      ? () => controller.zoomDown(duration: Duration.zero)
                      : null,
                  icon: const Icon(Icons.zoom_out),
                ),
                IconButton(
                  tooltip: 'Acercar documento',
                  onPressed: ready
                      ? () => controller.zoomUp(duration: Duration.zero)
                      : null,
                  icon: const Icon(Icons.zoom_in),
                ),
              ],
            ),
          ),
          Expanded(
            child: FutureBuilder<Uint8List>(
              future: data,
              builder: (context, snapshot) {
                if (snapshot.hasError) {
                  return const Center(
                    child: Padding(
                      padding: EdgeInsets.all(24),
                      child: Text(
                        'No se puede abrir el documento: falta el archivo o su integridad no coincide.',
                      ),
                    ),
                  );
                }
                if (!snapshot.hasData) {
                  return const Center(child: CircularProgressIndicator());
                }
                return PdfViewer.data(
                  snapshot.data!,
                  sourceName: 'wellq-reviewed-synthetic.pdf',
                  controller: controller,
                  params: PdfViewerParams(
                    imageCacheBudget: budget,
                    onViewerReady: (document, _) {
                      if (mounted) {
                        setState(() {
                          ready = true;
                          pages = document.pages.length;
                        });
                      }
                    },
                    errorBannerBuilder: (context, _, trace, ref) =>
                        const Center(
                          child: Text(
                            'No se pudo representar el PDF sintético.',
                          ),
                        ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    ),
  );
}
