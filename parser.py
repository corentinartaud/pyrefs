from typing import List, Dict
import abc, re

from config import (
  TAG_KEY_MAPPING, LIST_TYPE_TAGS, DELIMITED_TAG_MAPPING
)

class ParserError(Exception): 
  pass

class Parser(abc.ABC):
  """Base Parser class."""
  START_TAG: str
  END_TAG: str = "ER"
  UNKNOWN_TAG: str = "UK"
  PATTERN: str
  DEFAULT_MAPPING: Dict
  DEFAULT_LIST_TAGS: List[str]
  DEFAULT_DELIMITER_MAPPING: Dict
  
  def __init__(self, mapping=None, list_tags=None, delimiter=None, enforce_list_tags=True, newline=None):
    self.pattern = re.compile(self.PATTERN)
    self.mapping = mapping if mapping is not None else self.DEFAULT_MAPPING
    self.list_tags = list_tags if list_tags is not None else self.DEFAULT_LIST_TAGS
    self.delimiter = delimiter if delimiter is not None else self.DEFAULT_DELIMITER_MAPPING
    self.enforce_list_tags = enforce_list_tags
  
  @abc.abstractmethod
  def content(self, line: str):
    raise NotImplementedError

  def parselines(self, lines) -> List:
    content, data, self.inref = [], {}, False
    for i, line in enumerate(lines):
      if i == 0: line = line.lstrip("\uefeff")
      if not line.strip(): continue
      if bool(self.pattern.match(line)): # Determine if a line has a tag using regex
        if self._parse_tag(i, line, data):
          content.append(data)
          data, self.inref = {}, False
    return content
    
  def _parse_tag(self, index, line, data):
    match (tag := line[0:2]):
      case self.START_TAG:
        if self.inref: raise ParserError(f"Missing end of record tag in line {index}:\n {line}")
        self._add_tag(tag, line, data)
        self.inref = True
      case self.END_TAG: return data
      case _: (tag in self.mapping) and self._add_tag(tag, line, data)

  def _add_tag(self, tag, line, data):
    name, value = self.mapping[tag], self.content(line)
    if (delimiter := self.delimiter.get(tag)) is not None: raise Exception
    if tag in self.list_tags: self._add_list_tag(name, value, data)
    else: self._add_single_tag(name, value, data)

  def _add_single_tag(self, name, value, data):
    if self.enforce_list_tags or (name not in data):
      data.setdefault(name, value)

  def _add_list_tag(self, name, value, data):
    value = value if isinstance(value, list) else [value]
    if not data.get(name): data[name] = value
    else: data[name].extend(value)


class RisParser(Parser):
  START_TAG = "TY"
  PATTERN = r"^[A-Z][A-Z0-9]  - |^ER  -\s*$"
  DEFAULT_MAPPING = TAG_KEY_MAPPING
  DEFAULT_LIST_TAGS = LIST_TYPE_TAGS
  DEFAULT_DELIMITER_MAPPING = DELIMITED_TAG_MAPPING

  def content(self, line): return line[6:].strip()

def load(file, *, encoding = None, newline = None, parser = None, **kwargs):
  if parser is None: parser = RisParser
  if hasattr(file, "readline"): return parser(newline=newline, **kwargs).parselines(file)
  else: raise ValueError(f"File must be a file-like object or Path object, got `{type(file).__name__}`.")

def cite(content, newline: bool = True):
  # Currently only cites in APA format
  output = []
  for record in content:
    authors = list(map(lambda x: list(reversed(x.split(" "))), record["authors"]))
    sep = lambda i: ", &" if i == len(authors) - 2 and len(authors) > 1 else ","
    authors = " ".join([f"{a[0]}, {a[1][:1]}.{sep(i)}"  for i, a in enumerate(authors) if len(a) > 1])[:-1]
    rec = f"{authors} ({record.get('year', '')}). {record.get('primary_title', '')}. {record.get('journal_name', '')}. {record.get('doi', '')}"
    output.append(rec if not newline else rec + "\n")
  output = sorted(output)
  output = "\n".join(output)
  return output