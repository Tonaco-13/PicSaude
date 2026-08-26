#!/usr/bin/env python3
"""Pós-processamento do pacote DOCX (nível ZIP/XML):
1. Remove comentários de trabalho do Word (âncoras no document.xml + partes
   comments*.xml) — notas internas de revisão não podem ir à submissão final.
2. Corrige mc:Ignorable removendo prefixos não declarados no elemento raiz.
"""
import re
import shutil
import zipfile

SRC = "CBEB_PicSaude_FINAL_v9.docx"
TMP = "CBEB_PicSaude_FINAL_v9_clean.docx"

COMMENT_PARTS = {
    "word/comments.xml",
    "word/commentsExtended.xml",
    "word/commentsIds.xml",
    "word/commentsExtensible.xml",
    "word/people.xml",
}

zin = zipfile.ZipFile(SRC)
zout = zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED)

for item in zin.infolist():
    name = item.filename
    if name in COMMENT_PARTS:
        continue
    data = zin.read(name)

    if name == "word/document.xml":
        xml = data.decode("utf-8")
        # remove âncoras de comentário
        xml = re.sub(r"<w:commentRangeStart[^>]*/>", "", xml)
        xml = re.sub(r"<w:commentRangeEnd[^>]*/>", "", xml)
        # remove runs que só contêm commentReference
        xml = re.sub(
            r"<w:r\b[^>]*>(?:(?!</w:r>).)*?<w:commentReference[^>]*/>(?:(?!</w:r>).)*?</w:r>",
            "", xml, flags=re.S)
        # corrige mc:Ignorable: mantém só prefixos declarados no root
        root_end = xml.index(">", xml.index("<w:document"))
        root = xml[:root_end]
        declared = set(re.findall(r"xmlns:([A-Za-z0-9]+)=", root))
        m = re.search(r'mc:Ignorable="([^"]*)"', root)
        if m:
            keep = [t for t in m.group(1).split() if t in declared]
            new_root = re.sub(r'mc:Ignorable="[^"]*"',
                              f'mc:Ignorable="{" ".join(keep)}"', root)
            xml = new_root + xml[root_end:]
            print("mc:Ignorable:", m.group(1), "->", " ".join(keep))
        data = xml.encode("utf-8")

    elif name == "[Content_Types].xml":
        xml = data.decode("utf-8")
        xml = re.sub(
            r'<Override[^>]*PartName="/word/(comments|commentsExtended|commentsIds|'
            r'commentsExtensible|people)\.xml"[^>]*/>', "", xml)
        data = xml.encode("utf-8")

    elif name == "word/_rels/document.xml.rels":
        xml = data.decode("utf-8")
        xml = re.sub(
            r'<Relationship[^>]*Type="[^"]*/(comments|commentsExtended|commentsIds|'
            r'commentsExtensible|people)"[^>]*/>', "", xml)
        data = xml.encode("utf-8")

    zout.writestr(item, data)

zout.close()
zin.close()
shutil.move(TMP, SRC)
print("Pacote limpo:", SRC)
