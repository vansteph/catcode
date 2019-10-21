struct group_info init_groups = { .usage = ATOMIC_INIT(2) };

struct group_info *groups_alloc(int gidsetsize){

	struct group_info *group_info;

	int nblocks;

	int i;



	nblocks = (gidsetsize + NGROUPS_PER_BLOCK - 1) / NGROUPS_PER_BLOCK;

	/* Make sure we always allocate at least one indirect block pointer */

	nblocks = nblocks ? : 1;

	group_info = kmalloc(sizeof(*group_info) + nblocks*sizeof(gid_t *), GFP_USER);

	if (!group_info)

		return NULL;

	group_info->ngroups = gidsetsize;

	group_info->nblocks = nblocks;

	atomic_set(&group_info->usage, 1);



	if (gidsetsize <= NGROUPS_SMALL)

		group_info->blocks[0] = group_info->small_block;

	else {

		for (i = 0; i < nblocks; i++) {

			gid_t *b;

			b = (void *)_get_free_page(GFP_USER);

			if (!b)

				goto out_undo_partial_alloc;

			group_info->blocks[i] = b;

		}

	}

	return group_info;



out_undo_partial_alloc:

	while (--i >= 0) {

		free_page((unsigned long)group_info->blocks[i]);

	}

	kfree(group_info);

	return NULL;

}



/* fill a group_info from a user-space array - it must be allocated already */

static int groups_from_user(struct group_info *group_info,

    gid_t _user *grouplist)

{

	int i;

	unsigned int count = group_info->ngroups;



	for (i = 0; i < group_info->nblocks; i++) {

		unsigned int cp_count = min(NGROUPS_PER_BLOCK, count);

		unsigned int len = cp_count * sizeof(*grouplist);



		if (copy_from_user(group_info->blocks[i], grouplist, len))

			return -EFAULT;



		grouplist += NGROUPS_PER_BLOCK;

		count -= cp_count;

	}

	return 0;

}



/* a simple bsearch */

int groups_search(const struct group_info *group_info, gid_t grp)

{

	unsigned int left, right;



	if (!group_info)

		return 0;



	left = 0;

	right = group_info->ngroups;

	while (left < right) {

		unsigned int mid = left + (right - left)/2;

		if (grp > GROUP_AT(group_info, mid))

			left = mid + 1;

		else if (grp < GROUP_AT(group_info, mid))

			right = mid;

		else

			return 1;

	}

	return 0;

}



/**

 * set_groups - Change a group subscription in a set of credentials

 * @new: The newly prepared set of credentials to alter

 * @group_info: The group list to install

 *

 * Validate a group subscription and, if valid, insert it into a set

 * of credentials.

 */

int set_groups(struct cred *new, struct group_info *group_info)

{

	put_group_info(new->group_info);

	groups_sort(group_info);

	get_group_info(group_info);

	new->group_info = group_info;

	return 0;

}



EXPORT_SYMBOL(set_groups);



/**

 * set_current_groups - Change current's group subscription

 * @group_info: The group list to impose

 *

 * Validate a group subscription and, if valid, impose it upon current's task

 * security record.

 */

int set_current_groups(struct group_info *group_info)

{

	struct cred *new;

	int ret;



	new = prepare_creds();

	if (!new)

		return -ENOMEM;



	ret = set_groups(new, group_info);

	if (ret < 0) {

		abort_creds(new);

		return ret;

	}



	return commit_creds(new);

}