## 1.2
- *Feature removed* Deferred subclasses no longer support dynamic routing as the use case can be solved with different Deferred classes at router handler level.

## 1.1.1

- *Bugfix* Router failed to get routers from a Deferred subclass.
- *Changed* Route registration now raises an error for reserved parameter names.

## 1.1

- *Feature* Deferred subclasses now support dynamic routing via `self.routers` list