#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import abc

from neutron_lib import exceptions
from oslo_db import exception as obj_exc
from oslo_log import log
from oslo_utils import reflection
from oslo_versionedobjects import base as obj_base
from oslo_versionedobjects import fields as obj_fields
import six

from neutron._i18n import _
from neutron.objects.db import api as obj_db_api


LOG = log.getLogger(__name__)


class NeutronObjectUpdateForbidden(exceptions.NeutronException):
    message = _("Unable to update the following object fields: %(fields)s")


class NeutronDbObjectDuplicateEntry(exceptions.Conflict):
    message = _("Failed to create a duplicate %(object_type)s: "
                "for attribute(s) %(attributes)s with value(s) %(values)s")

    def __init__(self, object_class, db_exception):
        super(NeutronDbObjectDuplicateEntry, self).__init__(
            object_type=reflection.get_class_name(object_class,
                                                  fully_qualified=False),
            attributes=db_exception.columns,
            values=db_exception.value)


class NeutronPrimaryKeyMissing(exceptions.BadRequest):
    message = _("For class %(object_type)s missing primary keys: "
                "%(missing_keys)s")

    def __init__(self, object_class, missing_keys):
        super(NeutronPrimaryKeyMissing, self).__init__(
            object_type=reflection.get_class_name(object_class,
                                                  fully_qualified=False),
            missing_keys=missing_keys
        )


class NeutronSynthethicFieldMultipleForeignKeys(exceptions.NeutronException):
    message = _("Synthetic field %(fields)s shouldn't have more than one "
                "foreign key")


def get_updatable_fields(cls, fields):
    fields = fields.copy()
    for field in cls.fields_no_update:
        if field in fields:
            del fields[field]
    return fields


@six.add_metaclass(abc.ABCMeta)
class NeutronObject(obj_base.VersionedObject,
                    obj_base.VersionedObjectDictCompat,
                    obj_base.ComparableVersionedObject):

    synthetic_fields = []

    def __init__(self, context=None, **kwargs):
        super(NeutronObject, self).__init__(context, **kwargs)
        self.obj_set_defaults()

    def to_dict(self):
        dict_ = dict(self.items())
        for field in self.synthetic_fields:
            if field in dict_:
                if isinstance(dict_[field], list):
                    dict_[field] = [obj.to_dict() for obj in dict_[field]]
                else:
                    dict_[field] = (
                        dict_[field].to_dict() if dict_[field] else None)
        return dict_

    @classmethod
    def clean_obj_from_primitive(cls, primitive, context=None):
        obj = cls.obj_from_primitive(primitive, context)
        obj.obj_reset_changes()
        return obj

    @classmethod
    def get_object(cls, context, **kwargs):
        raise NotImplementedError()

    @classmethod
    def validate_filters(cls, **kwargs):
        bad_filters = [key for key in kwargs
                       if key not in cls.fields or key in cls.synthetic_fields]
        if bad_filters:
            bad_filters = ', '.join(bad_filters)
            msg = _("'%s' is not supported for filtering") % bad_filters
            raise exceptions.InvalidInput(error_message=msg)

    @classmethod
    @abc.abstractmethod
    def get_objects(cls, context, **kwargs):
        raise NotImplementedError()

    def create(self):
        raise NotImplementedError()

    def update(self):
        raise NotImplementedError()

    def delete(self):
        raise NotImplementedError()


class NeutronDbObject(NeutronObject):

    # should be overridden for all persistent objects
    db_model = None

    primary_keys = ['id']

    # a dict to store the association between the foreign key and the
    # corresponding key in the main table
    foreign_keys = {}

    fields_no_update = []

    def from_db_object(self, *objs):
        for field in self.fields:
            for db_obj in objs:
                if field in db_obj and field not in self.synthetic_fields:
                    setattr(self, field, db_obj[field])
                break
        self.load_synthetic_db_fields()
        self.obj_reset_changes()

    @classmethod
    def _load_object(cls, context, db_obj):
        obj = cls(context)
        for field in obj.fields:
            if field not in obj.synthetic_fields and field in db_obj:
                setattr(obj, field, db_obj[field])
        obj.load_synthetic_db_fields()
        obj.obj_reset_changes()
        return obj

    @classmethod
    def get_object(cls, context, **kwargs):
        """
        This method fetches object from DB and convert it to versioned
        object.

        :param context:
        :param kwargs: multiple primary keys defined key=value pairs
        :return: single object of NeutronDbObject class
        """
        missing_keys = set(cls.primary_keys).difference(kwargs.keys())
        if missing_keys:
            raise NeutronPrimaryKeyMissing(object_class=cls.__class__,
                                           missing_keys=missing_keys)

        db_obj = obj_db_api.get_object(context, cls.db_model, **kwargs)
        if db_obj:
            return cls._load_object(context, db_obj)

    @classmethod
    def get_objects(cls, context, **kwargs):
        cls.validate_filters(**kwargs)
        db_objs = obj_db_api.get_objects(context, cls.db_model, **kwargs)
        return [cls._load_object(context, db_obj) for db_obj in db_objs]

    @classmethod
    def is_accessible(cls, context, db_obj):
        return (context.is_admin or
                context.tenant_id == db_obj.tenant_id)

    def _get_changed_persistent_fields(self):
        fields = self.obj_get_changes()
        for field in self.synthetic_fields:
            if field in fields:
                del fields[field]
        return fields

    def _validate_changed_fields(self, fields):
        fields = fields.copy()
        # We won't allow id update anyway, so let's pop it out not to trigger
        # update on id field touched by the consumer
        fields.pop('id', None)

        forbidden_updates = set(self.fields_no_update) & set(fields.keys())
        if forbidden_updates:
            raise NeutronObjectUpdateForbidden(fields=forbidden_updates)

        return fields

    def load_synthetic_db_fields(self):
        """
        This method loads the synthetic fields that are store in a different
        table from the main object

        This method doesn't take care of loading synthetic fields that aren't
        stored in the DB, e.g. 'shared' in rbac policy
        """

        # TODO(rossella_s) Find a way to handle ObjectFields with
        # subclasses=True
        for field in self.synthetic_fields:
            try:
                objclasses = obj_base.VersionedObjectRegistry.obj_classes(
                ).get(self.fields[field].objname)
            except AttributeError:
                LOG.debug("Synthetic field %s is not an ObjectField", field)
                continue
            if not objclasses:
                # NOTE(rossella_s) some synthetic fields are not handled by
                # this method, for example the ones that have subclasses, see
                # QosRule
                break
            objclass = objclasses[0]
            if len(objclass.foreign_keys.keys) > 1:
                raise NeutronSynthethicFieldMultipleForeignKeys(field=field)
            objs = objclass.get_objects(
                self._context,
                **{objclass.foreign_keys.keys[0]: getattr(
                    self, self.foreign_key.values[0])})
            if objs:
                if isinstance(self.fields[field], obj_fields.ObjectField):
                    setattr(self, field, objs[0])
                else:
                    setattr(self, field, objs)
            else:
                setattr(self, field, None)
            self.obj_reset_changes([field])

    def create(self):
        fields = self._get_changed_persistent_fields()
        try:
            db_obj = obj_db_api.create_object(self._context, self.db_model,
                                              fields)
        except obj_exc.DBDuplicateEntry as db_exc:
            raise NeutronDbObjectDuplicateEntry(object_class=self.__class__,
                                                db_exception=db_exc)

        self.from_db_object(db_obj)

    def _get_composite_keys(self):
        keys = {}
        for key in self.primary_keys:
            keys[key] = getattr(self, key)
        return keys

    def update(self):
        updates = self._get_changed_persistent_fields()
        updates = self._validate_changed_fields(updates)

        if updates:
            db_obj = obj_db_api.update_object(self._context, self.db_model,
                                              updates,
                                              **self._get_composite_keys())
            self.from_db_object(self, db_obj)

    def delete(self):
        obj_db_api.delete_object(self._context, self.db_model,
                                 **self._get_composite_keys())
